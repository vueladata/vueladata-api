"""Endpoints HTTP de pasajeros: RF-06, RN-11 y RNF-04.

Las pruebas usan SQLite en memoria (no requieren PostgreSQL). Se crean las tablas
de `shared.models` y solo las tablas propias de `app.models` que usa el CRUD de
pasajeros (reserva, regla_compensacion, compensacion, pago).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, SmallInteger, create_engine, event
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # registra todas las tablas del dominio F7
import shared.models  # registra todas las tablas del grafo del pasajero
from app.database import Base as AppBase
from app.database import get_db
from app.main import app
from app.models.compensacion import Compensacion
from app.models.pago import Pago
from app.models.regla_compensacion import ReglaCompensacion
from app.models.reserva import Reserva
from shared import models
from shared.models.base import Base as SharedBase


@compiles(BigInteger, "sqlite")
def _bigint_como_integer(tipo, compilador, **kw):
    return "INTEGER"


@compiles(SmallInteger, "sqlite")
def _smallint_como_integer(tipo, compilador, **kw):
    return "INTEGER"


def utc(dia, hora, minuto=0):
    return datetime(2026, 11, dia, hora, minuto, tzinfo=timezone.utc)


@pytest.fixture
def motor():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"vueladata": None}},
    )
    SharedBase.metadata.create_all(engine)
    # `create_all(tables=...)` resuelve las FKs contra el metadata completo de la app,
    # pero solo crea las tablas propias que no existen en shared.models.
    AppBase.metadata.create_all(
        engine,
        tables=[
            Reserva.__table__,
            ReglaCompensacion.__table__,
            Compensacion.__table__,
            Pago.__table__,
        ],
    )
    return engine


@pytest.fixture
def sesion(motor):
    Session = sessionmaker(bind=motor)
    db = Session()
    sembrar(db)
    yield db
    db.close()


@pytest.fixture
def client(sesion):
    def override_get_db():
        try:
            yield sesion
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def sembrar(db):
    db.add_all(
        [
            models.Aeropuerto(id_aeropuerto=1, id_ciudad=1, codigo_iata="BOG", nombre="El Dorado",
                              latitud=Decimal("4.70"), longitud=Decimal("-74.14"),
                              zona_horaria="America/Bogota", es_hub=True),
            models.Aeropuerto(id_aeropuerto=2, id_ciudad=2, codigo_iata="MDE", nombre="José María Córdova",
                              latitud=Decimal("6.16"), longitud=Decimal("-75.42"),
                              zona_horaria="America/Bogota", es_hub=False),
            models.Aeropuerto(id_aeropuerto=3, id_ciudad=3, codigo_iata="MIA", nombre="Miami International",
                              latitud=Decimal("25.79"), longitud=Decimal("-80.29"),
                              zona_horaria="America/New_York", es_hub=False),
            models.Ruta(id_ruta=1, id_aeropuerto_origen=2, id_aeropuerto_destino=1, duracion_estimada_min=60),
            models.Ruta(id_ruta=2, id_aeropuerto_origen=1, id_aeropuerto_destino=3, duracion_estimada_min=240),
            models.EstadoVuelo(id_estado_vuelo=1, codigo="PROGRAMADO", nombre="Programado"),
            models.Causa(id_causa=1, codigo="TECNICA", nombre="Falla técnica", es_imputable=True),
            models.Vuelo(id_vuelo=1, id_ruta=1, id_aeronave=1, numero_vuelo="AC100",
                         salida_programada_utc=utc(5, 13), llegada_programada_utc=utc(5, 14),
                         id_estado_vuelo_actual=1),
            models.Vuelo(id_vuelo=2, id_ruta=2, id_aeronave=2, numero_vuelo="AC200",
                         salida_programada_utc=utc(5, 15), llegada_programada_utc=utc(5, 19),
                         id_estado_vuelo_actual=1),
            models.Vuelo(id_vuelo=3, id_ruta=1, id_aeronave=1, numero_vuelo="AC102",
                         salida_programada_utc=utc(5, 18), llegada_programada_utc=utc(5, 19),
                         id_estado_vuelo_actual=1),
            models.Vuelo(id_vuelo=4, id_ruta=1, id_aeronave=3, numero_vuelo="AC300",
                         salida_programada_utc=utc(5, 20), llegada_programada_utc=utc(5, 21),
                         id_estado_vuelo_actual=1),
            models.Pasajero(id_pasajero=1, nombre="Ana", apellido="Ríos", documento="111",
                            tipo_documento="CC", fecha_nacimiento=date(1990, 1, 1),
                            correo="ana@example.com"),
            models.Pasajero(id_pasajero=2, nombre="Beto", apellido="Ríos", documento="222",
                            tipo_documento="CC", fecha_nacimiento=date(1992, 2, 2),
                            correo="beto@example.com"),
            # Ana: reserva ABC123 (2 tramos) y reserva XYZ999 (1 tramo).
            models.ReservaPasajero(id_reserva_pasajero=1, id_reserva=1, id_pasajero=1),
            models.ReservaPasajero(id_reserva_pasajero=2, id_reserva=2, id_pasajero=1),
            # Beto: reserva BETO01.
            models.ReservaPasajero(id_reserva_pasajero=3, id_reserva=3, id_pasajero=2),
            models.Itinerario(id_itinerario=1, id_reserva_pasajero=1, fecha_salida_utc=utc(5, 13),
                              estado="ACTIVO", fecha_creacion_utc=utc(1, 0),
                              fecha_actualizacion_utc=utc(1, 0)),
            models.Itinerario(id_itinerario=2, id_reserva_pasajero=2, fecha_salida_utc=utc(5, 18),
                              estado="ACTIVO", fecha_creacion_utc=utc(1, 0),
                              fecha_actualizacion_utc=utc(1, 0)),
            models.Itinerario(id_itinerario=3, id_reserva_pasajero=3, fecha_salida_utc=utc(5, 20),
                              estado="ACTIVO", fecha_creacion_utc=utc(1, 0),
                              fecha_actualizacion_utc=utc(1, 0)),
            models.DetalleReserva(id_detalle_reserva=1, id_itinerario=1, id_vuelo=1, numero_secuencia=1,
                                  clase_servicio="ECONOMICA", monto_tarifa_pagada=Decimal("200.00"),
                                  moneda="USD", numero_asiento="12A", estado_segmento="CONFIRMADO"),
            models.DetalleReserva(id_detalle_reserva=2, id_itinerario=1, id_vuelo=2, numero_secuencia=2,
                                  clase_servicio="ECONOMICA", monto_tarifa_pagada=Decimal("400.00"),
                                  moneda="USD", numero_asiento="20C", estado_segmento="CONFIRMADO"),
            models.DetalleReserva(id_detalle_reserva=3, id_itinerario=2, id_vuelo=3, numero_secuencia=1,
                                  clase_servicio="ECONOMICA", monto_tarifa_pagada=Decimal("180.00"),
                                  moneda="USD", numero_asiento="12B", estado_segmento="CONFIRMADO"),
            models.DetalleReserva(id_detalle_reserva=4, id_itinerario=3, id_vuelo=4, numero_secuencia=1,
                                  clase_servicio="ECONOMICA", monto_tarifa_pagada=Decimal("150.00"),
                                  moneda="USD", numero_asiento="1A", estado_segmento="CONFIRMADO"),
            models.TiempoMinimoConexion(id_regla_conexion=1, id_aeropuerto=1, tipo_llegada="NACIONAL",
                                        tipo_salida="INTERNACIONAL", minutos_minimos=50,
                                        vigente_desde_utc=utc(1, 0)),
            models.ConexionItinerario(id_conexion=1, id_regla_conexion=1,
                                      id_detalle_reserva_llegada=1, id_detalle_reserva_salida=2),
            models.EvaluacionConexion(id_evaluacion=1, id_conexion=1, fecha_evaluacion_utc=utc(5, 13),
                                      llegada_estimada_utc=utc(5, 14), salida_estimada_utc=utc(5, 15),
                                      minutos_disponibles=60, minutos_requeridos=50, estado="EN_RIESGO"),
            models.Reubicacion(id_reubicacion=1, id_detalle_reserva=1, id_incidencia=1,
                               id_vuelo_propuesto=3, estado="OFRECIDA", fecha_oferta_utc=utc(5, 13)),
            models.Notificacion(id_notificacion=1, id_detalle_reserva=1, id_compensacion=1,
                                tipo="COMPENSACION", canal="EMAIL", estado_envio="ENVIADA",
                                fecha_programada_utc=utc(5, 14), fecha_envio_utc=utc(5, 14)),
            models.Notificacion(id_notificacion=2, id_detalle_reserva=3, id_compensacion=2,
                                tipo="COMPENSACION", canal="EMAIL", estado_envio="PENDIENTE",
                                fecha_programada_utc=utc(5, 19)),
            Reserva(id_reserva=1, codigo_reserva="ABC123", fecha_reserva_utc=utc(1, 0),
                    estado_reserva="CONFIRMADA", fecha_actualizacion_utc=utc(2, 0)),
            Reserva(id_reserva=2, codigo_reserva="XYZ999", fecha_reserva_utc=utc(1, 0),
                    estado_reserva="CONFIRMADA", fecha_actualizacion_utc=utc(2, 0)),
            Reserva(id_reserva=3, codigo_reserva="BETO01", fecha_reserva_utc=utc(1, 0),
                    estado_reserva="CONFIRMADA", fecha_actualizacion_utc=utc(2, 0)),
            ReglaCompensacion(id_regla_compensacion=1, tipo_incidencia="RETRASO", minutos_minimos=120,
                              minutos_maximos=240, aviso_max_horas=None, porcentaje=Decimal("0.2500"),
                              requiere_reubicacion=False, vigente_desde_utc=utc(1, 0)),
            Compensacion(id_compensacion=1, id_detalle_reserva=1, id_incidencia=1,
                         id_regla_compensacion=1, minutos_imputables=150, monto=Decimal("50.00"),
                         moneda="USD", fecha_calculo_utc=utc(5, 15), estado="CALCULADA"),
            Compensacion(id_compensacion=2, id_detalle_reserva=3, id_incidencia=1,
                         id_regla_compensacion=1, minutos_imputables=150, monto=Decimal("45.00"),
                         moneda="USD", fecha_calculo_utc=utc(5, 19), estado="CALCULADA"),
            Compensacion(id_compensacion=3, id_detalle_reserva=4, id_incidencia=1,
                         id_regla_compensacion=1, minutos_imputables=200, monto=Decimal("30.00"),
                         moneda="USD", fecha_calculo_utc=utc(5, 21), estado="CALCULADA"),
            Pago(id_pago=1, id_compensacion=1, clave_idempotencia="abc",
                 estado="PENDIENTE", fecha_solicitud_utc=utc(5, 15),
                 fecha_actualizacion_utc=utc(5, 15)),
        ]
    )
    db.commit()


# ── OpenAPI ───────────────────────────────────────────────────────────────


def test_openapi_documenta_endpoints_de_pasajeros(client):
    schema = client.get("/openapi.json").json()
    assert "/pasajeros/{id_pasajero}" in schema["paths"]
    assert "/pasajeros/{id_pasajero}/itinerarios" in schema["paths"]
    assert "/pasajeros/{id_pasajero}/reservas" in schema["paths"]
    assert "/pasajeros/{id_pasajero}/compensaciones" in schema["paths"]
    assert "/reservas/{codigo_reserva}/estado" in schema["paths"]
    assert "Pasajeros" in [tag["name"] for tag in schema.get("tags", [])]


# ── RN-11: identidad y privacidad ─────────────────────────────────────────


def test_perfil_sin_cabecera_devuelve_401(client):
    assert client.get("/pasajeros/1").status_code == 401


def test_perfil_de_otro_pasajero_devuelve_403(client):
    respuesta = client.get("/pasajeros/1", headers={"X-Pasajero-Id": "2"})
    assert respuesta.status_code == 403


def test_perfil_propio_devuelve_datos(client):
    respuesta = client.get("/pasajeros/1", headers={"X-Pasajero-Id": "1"})
    assert respuesta.status_code == 200
    assert respuesta.json()["correo"] == "ana@example.com"


def test_itinerarios_solo_del_pasajero(client):
    respuesta = client.get("/pasajeros/1/itinerarios", headers={"X-Pasajero-Id": "1"})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    codigos = {r["codigo_reserva"] for r in datos["reservas"]}
    assert codigos == {"ABC123", "XYZ999"}
    assert "BETO01" not in codigos


def test_compensaciones_solo_del_pasajero(client):
    respuesta = client.get("/pasajeros/1/compensaciones", headers={"X-Pasajero-Id": "1"})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    ids = {c["id_compensacion"] for c in datos["compensaciones"]}
    assert ids == {1, 2}
    assert datos["resumen"]["total_compensaciones"] == 2
    assert datos["resumen"]["monto_total"] == "95.00"


# ── Estado por código de reserva (RN-11 + aislamiento de datos) ───────────


def test_estado_reserva_no_mezcla_otras_reservas_del_mismo_pasajero(client):
    respuesta = client.get("/reservas/ABC123/estado", headers={"X-Pasajero-Id": "1"})
    assert respuesta.status_code == 200
    datos = respuesta.json()

    # ABC123 tiene exactamente 2 tramos; XYZ999 (también de Ana) no debe aparecer.
    assert datos["resumen"]["total_vuelos"] == 2
    assert {c["id_compensacion"] for c in datos["compensaciones"]} == {1}
    assert datos["resumen"]["total_compensaciones"] == 1
    assert datos["resumen"]["monto_compensado"] == "50.00"


def test_estado_reserva_de_otro_pasajero_devuelve_403(client):
    respuesta = client.get("/reservas/ABC123/estado", headers={"X-Pasajero-Id": "2"})
    assert respuesta.status_code == 403


def test_estado_reserva_inexistente_devuelve_404(client):
    respuesta = client.get("/reservas/NOEXISTE/estado", headers={"X-Pasajero-Id": "1"})
    assert respuesta.status_code == 404


# ── RNF-04: sin N+1 ───────────────────────────────────────────────────────


def test_itinerarios_no_hacen_consultas_n_plus_1(client, sesion, motor):
    consultas = []

    def contar(conn, cursor, statement, parameters, context, executemany):
        consultas.append(statement)

    event.listen(motor, "before_cursor_execute", contar)
    try:
        assert client.get("/pasajeros/1/itinerarios", headers={"X-Pasajero-Id": "1"}).status_code == 200
        consultas_con_2_tramos = len(consultas)

        # Agregamos 5 tramos más al mismo itinerario: si hubiera N+1, las consultas crecerían.
        for secuencia in range(3, 8):
            sesion.add(
                models.DetalleReserva(
                    id_detalle_reserva=100 + secuencia,
                    id_itinerario=1,
                    id_vuelo=1,
                    numero_secuencia=secuencia,
                    clase_servicio="ECONOMICA",
                    monto_tarifa_pagada=Decimal("100.00"),
                    moneda="USD",
                    numero_asiento=f"3{secuencia}A",
                    estado_segmento="CONFIRMADO",
                )
            )
        sesion.commit()
        consultas.clear()

        assert client.get("/pasajeros/1/itinerarios", headers={"X-Pasajero-Id": "1"}).status_code == 200
        consultas_con_7_tramos = len(consultas)
    finally:
        event.remove(motor, "before_cursor_execute", contar)

    assert consultas_con_7_tramos == consultas_con_2_tramos
