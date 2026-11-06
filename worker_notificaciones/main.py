import json
import time

from shared.db_session import SessionLocal
from shared.notificaciones import COLA_EMAIL, declarar_topologia
from shared.rabbit_client import conectar_rabbitmq
from worker_notificaciones.correo import EnviadorGmail
from worker_notificaciones.procesador import procesar_mensaje

# Un mensaje a la vez: cada uno puede generar muchos correos.
PREFETCH = 1

enviador = EnviadorGmail()


def callback(ch, method, properties, body):
    """
    Manejo de ACK/NACK igual que worker_rds:
    - ACK cuando el mensaje se procesó, aunque algún correo haya fallado (queda FALLIDA en la tabla notificacion).
    - ACK y descarte si el mensaje no es JSON válido (no tiene sentido reintentarlo).
    - NACK con requeue=True si falla la base de datos, para reintentar más tarde.
    """
    db = SessionLocal()
    try:
        try:
            datos = json.loads(body)
        except Exception as e:
            print(f"[Worker Notificaciones] ❌ Mensaje no es JSON válido: {e}. Descartando (ACK).", flush=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        resumen = procesar_mensaje(db, method.routing_key, datos, enviador)
        print(
            f"[Worker Notificaciones] {method.routing_key} | enviados={resumen['enviados']} "
            f"omitidos={resumen['omitidos']} fallidos={resumen['fallidos']}",
            flush=True,
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        db.rollback()
        print(f"[Worker Notificaciones] 💥 ERROR con tag {method.delivery_tag}: {e}. Reintento en 5 s.", flush=True)
        time.sleep(5)  # evita reintentar sin pausa si la base está caída
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        db.close()


def main():
    print("[Worker Notificaciones] Iniciando servicio de correos...", flush=True)
    if not enviador.esta_configurado():
        raise SystemExit("[Worker Notificaciones] Faltan SMTP_USUARIO o SMTP_CLAVE en las variables de entorno.")

    connection = conectar_rabbitmq()
    channel = connection.channel()
    declarar_topologia(channel)
    channel.basic_qos(prefetch_count=PREFETCH)
    channel.basic_consume(queue=COLA_EMAIL, on_message_callback=callback)
    print(f"[Worker Notificaciones] Escuchando cola '{COLA_EMAIL}' (Ctrl+C para salir)...", flush=True)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[Worker Notificaciones] Deteniendo consumidor...", flush=True)
        channel.stop_consuming()
    finally:
        enviador.cerrar()
        if connection and connection.is_open:
            connection.close()
        print("[Worker Notificaciones] Finalizado limpiamente.", flush=True)


if __name__ == "__main__":
    main()
