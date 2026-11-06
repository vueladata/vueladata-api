"""Topología de RabbitMQ para las notificaciones a pasajeros.

    worker_rds ──publica──> exchange "vueladata.notificaciones" (tipo topic)
                                │  routing keys: vuelo.cancelado, vuelo.retrasado,
                                │                conexion.en_riesgo, itinerario.cambiado
                                ▼
                     cola "q.notificaciones_email" (durable)
                                ▼
                     worker_notificaciones ──> correo (Gmail SMTP)

Tanto el productor como el consumidor declaran todo esto. Declarar algo que ya existe no hace nada,
y así los mensajes no se pierden aunque el worker de correos aún no haya arrancado.
"""

import json
import uuid
from datetime import datetime, timezone

import pika

EXCHANGE_NOTIFICACIONES = "vueladata.notificaciones"
COLA_EMAIL = "q.notificaciones_email"

# Routing keys: qué pasó. El worker de correos decide qué correo enviar según la llave.
VUELO_CANCELADO = "vuelo.cancelado"
VUELO_RETRASADO = "vuelo.retrasado"
CONEXION_EN_RIESGO = "conexion.en_riesgo"
ITINERARIO_CAMBIADO = "itinerario.cambiado"

ROUTING_KEYS = [VUELO_CANCELADO, VUELO_RETRASADO, CONEXION_EN_RIESGO, ITINERARIO_CAMBIADO]


def declarar_topologia(channel) -> None:
    """Crea (si no existen) el exchange, la cola de correos y sus bindings."""
    channel.exchange_declare(exchange=EXCHANGE_NOTIFICACIONES, exchange_type="topic", durable=True)
    channel.queue_declare(queue=COLA_EMAIL, durable=True)
    for routing_key in ROUTING_KEYS:
        channel.queue_bind(queue=COLA_EMAIL, exchange=EXCHANGE_NOTIFICACIONES, routing_key=routing_key)


def publicar_notificacion(channel, routing_key: str, datos: dict) -> None:
    """Publica un mensaje persistente en el exchange de notificaciones.

    Si el canal tiene confirm_delivery() activo, basic_publish espera la confirmación (ACK)
    del broker y lanza una excepción si el mensaje no se pudo entregar a ninguna cola.
    """
    mensaje = {
        "id_mensaje": str(uuid.uuid4()),
        "tipo": routing_key,
        "fecha_publicacion_utc": datetime.now(timezone.utc).isoformat(),
        **datos,
    }
    channel.basic_publish(
        exchange=EXCHANGE_NOTIFICACIONES,
        routing_key=routing_key,
        body=json.dumps(mensaje, ensure_ascii=False, default=str).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),  # 2 = persistente
        mandatory=True,  # si ninguna cola recibe el mensaje, el broker lo devuelve en vez de botarlo
    )
