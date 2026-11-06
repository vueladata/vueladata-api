"""Configuración de las pruebas de los workers (worker_rds y worker_notificaciones).

No usan PostgreSQL, RabbitMQ ni Gmail:
- la base es SQLite en memoria con los modelos de shared/models,
- "publicar en RabbitMQ" se reemplaza por una lista que guarda los mensajes,
- "enviar por Gmail" se reemplaza por EnviadorFalso, que guarda los correos.
"""

import smtplib
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared import models
from shared.models.base import Base


# Solo en pruebas: SQLite solo genera ids automáticos en columnas INTEGER, no BIGINT.
@compiles(BigInteger, "sqlite")
def _bigint_como_integer_en_sqlite(tipo, compilador, **kw):
    return "INTEGER"


# SQLite no tiene schemas: ignoramos "vueladata" solo durante las pruebas.
motor_pruebas = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    execution_options={"schema_translate_map": {"vueladata": None}},
)
SesionPruebas = sessionmaker(bind=motor_pruebas)


def utc(anio, mes, dia, hora, minuto=0):
    return datetime(anio, mes, dia, hora, minuto, tzinfo=timezone.utc)


class EnviadorFalso:
    """Hace de Gmail: guarda los correos en una lista. Con fallar=True simula que Gmail no responde."""

    def __init__(self, fallar=False):
        self.fallar = fallar
        self.enviados = []

    def enviar(self, destinatario, asunto, cuerpo, html=None):
        if self.fallar:
            raise smtplib.SMTPException("Gmail no disponible")
        self.enviados.append({"para": destinatario, "asunto": asunto, "cuerpo": cuerpo, "html": html})


@pytest.fixture
def db():
    Base.metadata.create_all(motor_pruebas)
    sesion = SesionPruebas()
    crear_datos(sesion)
    yield sesion
    sesion.close()
    Base.metadata.drop_all(motor_pruebas)


@pytest.fixture
def publicados():
    """Lista de (routing_key, datos) que el worker_rds "publicó" en RabbitMQ."""
    return []


@pytest.fixture
def publicar(publicados):
    def _publicar(routing_key, datos):
        publicados.append((routing_key, datos))

    return _publicar


@pytest.fixture(autouse=True)
def sin_modo_pruebas(monkeypatch):
    # Cada prueba empieza sin EMAIL_DESTINO_PRUEBAS, aunque exista en tu .env.
    monkeypatch.delenv("EMAIL_DESTINO_PRUEBAS", raising=False)


def evento(codigo, id_vuelo, fecha, causa=None, id_externo=None):
    return {
        "id_externo_evento": id_externo or f"{codigo}-{id_vuelo}-{fecha.isoformat()}",
        "id_vuelo": id_vuelo,
        "codigo_evento": codigo,
        "fecha_hora_evento_utc": fecha.isoformat(),
        "codigo_causa_original": causa,
    }


def crear_datos(db):
    """Escenario:

    - AC100 MDE -> BOG, sale 13:00 UTC (08:00 hora Colombia), llega 14:00 UTC.
    - AC200 BOG -> MIA, sale 15:00 UTC. Ana conecta en BOG de AC100 a AC200
      (60 min disponibles, mínimo 50).
    - AC102 MDE -> BOG, sale 18:00 UTC: es la alternativa si se cancela AC100.
    - En AC100 viajan Ana (tiene correo) y Beto (NO tiene correo).
    """
    db.add_all(
        [
            models.Aeropuerto(id_aeropuerto=1, id_ciudad=1, codigo_iata="BOG", nombre="El Dorado",
                              latitud=Decimal("4.70159"), longitud=Decimal("-74.14690"),
                              zona_horaria="America/Bogota", es_hub=True),
            models.Aeropuerto(id_aeropuerto=2, id_ciudad=2, codigo_iata="MDE", nombre="José María Córdova",
                              latitud=Decimal("6.16454"), longitud=Decimal("-75.42310"),
                              zona_horaria="America/Bogota", es_hub=False),
            models.Aeropuerto(id_aeropuerto=3, id_ciudad=3, codigo_iata="MIA", nombre="Miami International",
                              latitud=Decimal("25.79325"), longitud=Decimal("-80.29056"),
                              zona_horaria="America/New_York", es_hub=False),
            models.Ruta(id_ruta=1, id_aeropuerto_origen=2, id_aeropuerto_destino=1, duracion_estimada_min=60),
            models.Ruta(id_ruta=2, id_aeropuerto_origen=1, id_aeropuerto_destino=3, duracion_estimada_min=240),
            models.EstadoVuelo(id_estado_vuelo=1, codigo="PROGRAMADO", nombre="Programado"),
            models.EstadoVuelo(id_estado_vuelo=9, codigo="CANCELADO", nombre="Cancelado"),
            models.Causa(id_causa=1, codigo="TECNICA", nombre="Falla técnica", es_imputable=True),
            models.Causa(id_causa=4, codigo="CLIMA", nombre="Clima adverso", es_imputable=False),
            models.Vuelo(id_vuelo=1, id_ruta=1, id_aeronave=1, numero_vuelo="AC100",
                         salida_programada_utc=utc(2026, 11, 5, 13), llegada_programada_utc=utc(2026, 11, 5, 14),
                         id_estado_vuelo_actual=1),
            models.Vuelo(id_vuelo=2, id_ruta=2, id_aeronave=2, numero_vuelo="AC200",
                         salida_programada_utc=utc(2026, 11, 5, 15), llegada_programada_utc=utc(2026, 11, 5, 19),
                         id_estado_vuelo_actual=1),
            models.Vuelo(id_vuelo=3, id_ruta=1, id_aeronave=1, numero_vuelo="AC102",
                         salida_programada_utc=utc(2026, 11, 5, 18), llegada_programada_utc=utc(2026, 11, 5, 19),
                         id_estado_vuelo_actual=1),
            models.Pasajero(id_pasajero=1, nombre="Ana", apellido="Ríos", documento="111", tipo_documento="CC",
                            fecha_nacimiento=date(1990, 1, 1), correo="ana@example.com"),
            models.Pasajero(id_pasajero=2, nombre="Beto", apellido="Ríos", documento="222", tipo_documento="CC",
                            fecha_nacimiento=date(1992, 2, 2), correo=None),
            models.ReservaPasajero(id_reserva_pasajero=1, id_reserva=1, id_pasajero=1),
            models.ReservaPasajero(id_reserva_pasajero=2, id_reserva=2, id_pasajero=2),
            models.Itinerario(id_itinerario=1, id_reserva_pasajero=1, fecha_salida_utc=utc(2026, 11, 5, 13),
                              estado="ACTIVO", fecha_creacion_utc=utc(2026, 10, 1, 0),
                              fecha_actualizacion_utc=utc(2026, 10, 1, 0)),
            models.Itinerario(id_itinerario=2, id_reserva_pasajero=2, fecha_salida_utc=utc(2026, 11, 5, 13),
                              estado="ACTIVO", fecha_creacion_utc=utc(2026, 10, 1, 0),
                              fecha_actualizacion_utc=utc(2026, 10, 1, 0)),
            models.DetalleReserva(id_detalle_reserva=1, id_itinerario=1, id_vuelo=1, numero_secuencia=1,
                                  clase_servicio="ECONOMICA", monto_tarifa_pagada=Decimal("200.00"), moneda="USD",
                                  numero_asiento="12A", estado_segmento="CONFIRMADO"),
            models.DetalleReserva(id_detalle_reserva=2, id_itinerario=1, id_vuelo=2, numero_secuencia=2,
                                  clase_servicio="ECONOMICA", monto_tarifa_pagada=Decimal("400.00"), moneda="USD",
                                  numero_asiento="20C", estado_segmento="CONFIRMADO"),
            models.DetalleReserva(id_detalle_reserva=3, id_itinerario=2, id_vuelo=1, numero_secuencia=1,
                                  clase_servicio="ECONOMICA", monto_tarifa_pagada=Decimal("180.00"), moneda="USD",
                                  numero_asiento="12B", estado_segmento="CONFIRMADO"),
            models.TiempoMinimoConexion(id_regla_conexion=1, id_aeropuerto=1, tipo_llegada="NACIONAL",
                                        tipo_salida="INTERNACIONAL", minutos_minimos=50,
                                        vigente_desde_utc=utc(2026, 1, 1, 0)),
            models.ConexionItinerario(id_conexion=1, id_regla_conexion=1, id_detalle_reserva_llegada=1,
                                      id_detalle_reserva_salida=2),
        ]
    )
    db.commit()
