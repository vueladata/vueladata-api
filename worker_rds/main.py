import os
import json
import pika
from shared.rabbit_client import conectar_rabbitmq
from shared.db_session import SessionLocal
from shared.notificaciones import declarar_topologia, publicar_notificacion
from worker_rds.handlers.oooi_handler import procesar_evento_oooi
from worker_rds.handlers.posicion_handler import procesar_posicion_aeronave
from worker_rds.handlers.clima_handler import procesar_observacion_clima

# Admite nombres de cola configurables o lista separada por comas
QUEUES_ENV = os.getenv("QUEUE_RDS", "q.rds_writer,q_rds_writer,eventos_oooi_queue")
QUEUES = [q.strip() for q in QUEUES_ENV.split(",") if q.strip()]
PREFETCH = int(os.getenv("PREFETCH_COUNT", "5"))

def callback(ch, method, properties, body):
    """
    Consumer callback con manejo estricto de ACK/NACK (HU-25):
    - ACK para: 'ok', 'duplicado' e 'invalido' (no reencolar veneno)
    - NACK con requeue=True para fallas temporales de infraestructura (ej. BD caída)
    """
    db = SessionLocal()
    try:
        try:
            payload = json.loads(body)
        except Exception as e:
            print(f"[Worker RDS] ❌ Mensaje no es JSON válido: {e}. Descartando (ACK).", flush=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Enrutamiento dinámico según el tipo de mensaje
        if "codigo_evento" in payload or "id_externo_evento" in payload:
            # Las notificaciones (cancelación, retraso, conexión, reubicación) salen por el mismo canal.
            def publicar(routing_key, datos):
                publicar_notificacion(ch, routing_key, datos)

            resultado = procesar_evento_oooi(payload, db, publicar=publicar)
            tipo_msg = f"OOOI ({payload.get('codigo_evento')})"
        elif "id_externo_posicion" in payload or ("latitud" in payload and "longitud" in payload):
            resultado = procesar_posicion_aeronave(payload, db)
            tipo_msg = "POSICION_OPENSKY"
        elif "id_aeropuerto" in payload or "temperatura_c" in payload or "velocidad_viento_kmh" in payload:
            resultado = procesar_observacion_clima(payload, db)
            tipo_msg = "CLIMA_OPENMETEO"
        else:
            print(f"[Worker RDS] ⚠️ Tipo de mensaje desconocido en cola '{method.routing_key}'. Descartando.", flush=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f"[Worker RDS] [{resultado.upper()}] Tipo: {tipo_msg} | Tag: {method.delivery_tag} | Cola: {method.routing_key}", flush=True)
        # ACK confirma que el mensaje se procesó (o descartó intencionalmente)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        db.rollback()
        print(f"[Worker RDS] 💥 ERROR al procesar tag {method.delivery_tag}: {e}", flush=True)
        # NACK con requeue=True asegura que vuelva a la cola si la BD tuvo un fallo transitorio
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        db.close()

def main():
    print("[Worker RDS] Iniciando servicio consumidor RDS...", flush=True)
    connection = conectar_rabbitmq()
    channel = connection.channel()

    # Exchange y cola de notificaciones a pasajeros (ver shared/notificaciones.py).
    declarar_topologia(channel)
    # Publisher confirms: cada publicación espera el ACK del broker antes de continuar.
    channel.confirm_delivery()

    for queue_name in QUEUES:
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        print(f"[Worker RDS] Escuchando cola '{queue_name}'...", flush=True)

    channel.basic_qos(prefetch_count=PREFETCH)
    print(f"[Worker RDS] Listo. Prefetch={PREFETCH}. Esperando mensajes (Ctrl+C para salir)...", flush=True)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[Worker RDS] Deteniendo consumidor...", flush=True)
        channel.stop_consuming()
    finally:
        if connection and connection.is_open:
            connection.close()
        print("[Worker RDS] Finalizado limpiamente.", flush=True)

if __name__ == "__main__":
    main()
