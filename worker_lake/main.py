import os
import json
import time
import threading
import pika
from shared.rabbit_client import conectar_rabbitmq
from worker_lake.s3_uploader import subir_lote

QUEUES_ENV = os.getenv("QUEUE_LAKE", "q.lake_writer,q_lake_writer,eventos_oooi_lake")
QUEUES = [q.strip() for q in QUEUES_ENV.split(",") if q.strip()]
FLUSH_N = int(os.getenv("LAKE_FLUSH_EVERY_N", "50"))
FLUSH_SEC = int(os.getenv("LAKE_FLUSH_EVERY_SECONDS", "60"))
PREFETCH = int(os.getenv("PREFETCH_COUNT", "100"))

_buffer = []
_tags = []
_lock = threading.Lock()
_ultimo_flush = time.time()

def _realizar_flush(channel):
    """
    Vacía el buffer hacia S3 Bronze y envía ACK a todos los mensajes confirmados.

    El ACK se envía SOLO después de que la escritura (S3 o fallback local) terminó bien.
    Si la escritura falla, el lote sigue en memoria y los mensajes quedan sin ACK para
    que RabbitMQ los reentregue.
    """
    global _buffer, _tags, _ultimo_flush
    with _lock:
        if not _buffer:
            _ultimo_flush = time.time()
            return
        lote_actual = list(_buffer)
        tags_actuales = list(_tags)

    try:
        subir_lote(lote_actual)
    except Exception as e:
        # No tocamos el buffer: los mensajes deben reintentarse y no se pierden.
        with _lock:
            _ultimo_flush = time.time()
        print(f"[Worker Lake] ❌ Falló la subida a S3: {e}. Los mensajes permanecen sin ACK.", flush=True)
        return False

    # La escritura quedó confirmada: recién ahora retiramos el lote y hacemos ACK.
    with _lock:
        del _buffer[: len(lote_actual)]
        del _tags[: len(tags_actuales)]
        _ultimo_flush = time.time()

    for tag in tags_actuales:
        try:
            channel.basic_ack(delivery_tag=tag)
        except Exception as e:
            print(f"[Worker Lake] Error al confirmar tag {tag}: {e}", flush=True)
    return True

def _temporizador_flush(connection, channel):
    """
    Hilo daemon que vigila el tiempo transcurrido desde el último flush.
    Usa connection.add_callback_threadsafe para no colisionar con el bucle de Pika.
    """
    while True:
        time.sleep(1)
        tiempo_transcurrido = time.time() - _ultimo_flush
        with _lock:
            tiene_elementos = len(_buffer) > 0

        if tiene_elementos and tiempo_transcurrido >= FLUSH_SEC:
            print(f"[Worker Lake] ⏱️ Timeout de {FLUSH_SEC}s alcanzado con {len(_buffer)} elementos. Forzando flush...", flush=True)
            try:
                connection.add_callback_threadsafe(lambda: _realizar_flush(channel))
            except Exception as e:
                print(f"[Worker Lake] No se pudo encolar callback de flush: {e}", flush=True)

def callback(ch, method, properties, body):
    """
    Recibe el mensaje crudo, lo acumula en memoria y evalúa el umbral de lote.
    """
    try:
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"raw_payload": body.decode("utf-8", errors="replace")}

        with _lock:
            _buffer.append(payload)
            _tags.append(method.delivery_tag)
            largo = len(_buffer)

        if largo >= FLUSH_N:
            print(f"[Worker Lake] 📦 Lote de {largo} mensajes alcanzado. Ejecutando flush...", flush=True)
            _realizar_flush(ch)

    except Exception as e:
        print(f"[Worker Lake] 💥 Error en callback: {e}", flush=True)

def main():
    print("[Worker Lake] Iniciando consumidor para Data Lake S3 Bronze...", flush=True)
    connection = conectar_rabbitmq()
    channel = connection.channel()

    for q in QUEUES:
        channel.queue_declare(queue=q, durable=True)
        channel.basic_consume(queue=q, on_message_callback=callback)
        print(f"[Worker Lake] Escuchando cola '{q}'...", flush=True)

    channel.basic_qos(prefetch_count=PREFETCH)

    # Iniciar hilo de flush periódico de forma thread-safe
    timer_thread = threading.Thread(
        target=_temporizador_flush,
        args=(connection, channel),
        daemon=True
    )
    timer_thread.start()

    print(f"[Worker Lake] Listo. Flush cada {FLUSH_N} msgs o cada {FLUSH_SEC}s. Esperando...", flush=True)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[Worker Lake] Deteniendo consumidor y guardando buffer pendiente...", flush=True)
        channel.stop_consuming()
        _realizar_flush(channel)
    finally:
        if connection and connection.is_open:
            connection.close()
        print("[Worker Lake] Finalizado limpiamente.", flush=True)

if __name__ == "__main__":
    main()
