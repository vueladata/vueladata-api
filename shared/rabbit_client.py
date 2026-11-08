import os
import time
import pika
from dotenv import load_dotenv

# Cargar variables de entorno si existe .env local
load_dotenv()

def conectar_rabbitmq(max_intentos: int = 10, espera: int = 3) -> pika.BlockingConnection:
    """
    Establece conexión robusta con RabbitMQ usando reintentos exponenciales/lineales.
    Reutilizable por ambos workers (RDS y Lake).
    """
    user = os.getenv("RABBITMQ_USER")
    password = os.getenv("RABBITMQ_PASS")
    if not user or not password:
        raise RuntimeError(
            "Faltan RABBITMQ_USER y/o RABBITMQ_PASS. "
            "En AWS se inyectan desde SSM (/vueladata/dev/rabbitmq/user y /password)."
        )
    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))

    creds = pika.PlainCredentials(user, password)
    params = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=creds,
        heartbeat=600,
        blocked_connection_timeout=300
    )

    for intento in range(1, max_intentos + 1):
        try:
            print(f"[*] Conectando a RabbitMQ en {host}:{port} (Intento {intento}/{max_intentos})...", flush=True)
            conn = pika.BlockingConnection(params)
            print(f"[+] Conectado exitosamente a RabbitMQ.", flush=True)
            return conn
        except (pika.exceptions.AMQPConnectionError, Exception) as e:
            print(f"[!] Intento {intento}/{max_intentos} fallido: {e}", flush=True)
            if intento < max_intentos:
                time.sleep(espera)
            else:
                print(f"[!] Error crítico: No se pudo conectar a RabbitMQ después de {max_intentos} intentos.", flush=True)
                raise
