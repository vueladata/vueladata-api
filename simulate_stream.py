import os
import json
import time
import uuid
import random
from datetime import datetime, timezone, timedelta
import pika
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")

QUEUE_RDS = "q_rds_writer"
QUEUE_LAKE = "q_lake_writer"

CAUSAS = ["TECNICA", "TRIPULACION", "OPERACIONAL", "CLIMA"]

def conectar():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=creds
    )
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=QUEUE_RDS, durable=True)
    ch.queue_declare(queue=QUEUE_LAKE, durable=True)
    return conn, ch

def publicar(ch, payload):
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    props = pika.BasicProperties(delivery_mode=2, content_type="application/json")
    # Enviar a ambos workers
    ch.basic_publish(exchange="", routing_key=QUEUE_RDS, body=body, properties=props)
    ch.basic_publish(exchange="", routing_key=QUEUE_LAKE, body=body, properties=props)

def simular_eventos(cantidad_vuelos: int = 5, delay_segundos: float = 0.5):
    print(f"[*] Iniciando generador de eventos de prueba ({cantidad_vuelos} vuelos)...")
    conn, ch = conectar()
    ahora = datetime.now(timezone.utc)
    total_enviados = 0

    try:
        # 1. Simular Eventos OOOI
        for i in range(1, cantidad_vuelos + 1):
            t_base = ahora + timedelta(minutes=i * 10)

            # El último vuelo se cancela: genera el correo de cancelación y el de reubicación.
            if i == cantidad_vuelos:
                msg = {
                    "id_externo_evento": str(uuid.uuid4()),
                    "id_vuelo": i,
                    "numero_vuelo": f"VU-{1000 + i}",
                    "codigo_evento": "CANCEL",
                    "fecha_hora_evento_utc": ahora.isoformat(),
                    "codigo_causa_original": "TECNICA",
                }
                publicar(ch, msg)
                total_enviados += 1
                print(f"[>] CANCEL | Vuelo VU-{1000 + i} [id_vuelo={i}] (Causa: TECNICA)")
                continue

            es_retrasado = random.choice([True, False])
            minutos_retraso = random.randint(20, 150) if es_retrasado else 0
            causa = random.choice(CAUSAS) if es_retrasado else None

            t_out = t_base + timedelta(minutes=minutos_retraso)
            t_off = t_out + timedelta(minutes=15)
            t_on = t_off + timedelta(minutes=50)
            t_in = t_on + timedelta(minutes=10)

            eventos = [
                ("OUT", t_out, causa),
                ("OFF", t_off, None),
                ("ON", t_on, None),
                ("IN", t_in, None)
            ]

            for codigo, f_hora, c_causa in eventos:
                msg = {
                    "id_externo_evento": str(uuid.uuid4()),
                    "id_vuelo": i,
                    "numero_vuelo": f"VU-{1000 + i}",
                    "codigo_evento": codigo,
                    "fecha_hora_evento_utc": f_hora.isoformat(),
                    "codigo_causa_original": c_causa
                }
                publicar(ch, msg)
                total_enviados += 1
                causa_txt = f" (Causa: {c_causa})" if c_causa else ""
                print(f"[>] OOOI {codigo} | Vuelo VU-{1000 + i} [id_vuelo={i}]{causa_txt}")
                if delay_segundos > 0:
                    time.sleep(delay_segundos)

        # 2. Simular Telemetría OpenSky
        print("\n[*] Enviando posiciones OpenSky...")
        for i in range(1, 4):
            pos_msg = {
                "id_externo_posicion": str(uuid.uuid4()),
                "id_aeronave": i,
                "fecha_hora_posicion_utc": ahora.isoformat(),
                "latitud": round(4.70 + (i * 0.1), 5),
                "longitud": round(-74.14 - (i * 0.1), 5),
                "altitud_m": 2500.0 + (i * 500),
                "velocidad_kmh": 450.0 + (i * 20),
                "rumbo_grados": 180.0,
                "en_tierra": False
            }
            publicar(ch, pos_msg)
            total_enviados += 1
            print(f"[>] Telemetria aeronave {i} | Alt: {pos_msg['altitud_m']}m | Vel: {pos_msg['velocidad_kmh']} km/h")
            if delay_segundos > 0:
                time.sleep(delay_segundos)

        # 3. Simular Observaciones Clima Open-Meteo
        print("\n[*] Enviando reportes meteorologicos Open-Meteo...")
        for id_aeropuerto in [1, 2, 3]:
            clima_msg = {
                "id_aeropuerto": id_aeropuerto,
                "fecha_hora_observacion_utc": ahora.isoformat(),
                "visibilidad_km": 10.0,
                "velocidad_viento_kmh": 20.0 + (id_aeropuerto * 12.0),
                "direccion_viento_grados": 120.0,
                "temperatura_c": 18.0 + id_aeropuerto,
                "precipitacion_mm": 0.0,
                "codigo_clima": "DESPEJADO" if id_aeropuerto < 3 else "TORMENTA"
            }
            publicar(ch, clima_msg)
            total_enviados += 1
            print(f"[>] Clima Aeropuerto {id_aeropuerto} | Temp: {clima_msg['temperatura_c']}C | Viento: {clima_msg['velocidad_viento_kmh']} km/h")
            if delay_segundos > 0:
                time.sleep(delay_segundos)

        print(f"\n[+] Finalizado: Se transmitieron {total_enviados} eventos a RabbitMQ y a los Workers.")
    finally:
        conn.close()

if __name__ == "__main__":
    simular_eventos(cantidad_vuelos=5, delay_segundos=0.2)
