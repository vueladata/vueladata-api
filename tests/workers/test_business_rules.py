"""Reglas de negocio del worker_rds y criterios de aceptación CA-01 a CA-05."""

from datetime import timedelta
from decimal import Decimal

from shared import models
from tests.workers.conftest import evento, utc
from worker_rds.business_rules import (
    calcular_porcentaje_compensacion,
    calcular_retraso_propagado,
    es_otp,
    evaluar_auditoria_climatica,
    evaluar_condiciones_adversas,
    generar_clave_idempotencia,
    generar_clave_idempotencia_segmento,
    minutos_rotacion,
    resolver_causa,
)
from worker_rds.handlers.oooi_handler import procesar_evento_oooi

SALIDA_AC100 = utc(2026, 11, 5, 13)


# ── CA-01 / RN-01: OTP ────────────────────────────────────────────────────


def test_ca01_otp_es_puntual_hasta_15_minutos():
    assert es_otp(14) is True
    assert es_otp(15) is True
    assert es_otp(16) is False
    assert es_otp(None) is None


# ── CA-02 / CA-03 / RN-05 / RN-06: escala de compensación ─────────────────


def test_ca02_escala_de_compensacion_por_retraso_imputable():
    assert calcular_porcentaje_compensacion(119, True) == Decimal("0.00")
    assert calcular_porcentaje_compensacion(120, True) == Decimal("25.00")
    assert calcular_porcentaje_compensacion(239, True) == Decimal("25.00")
    assert calcular_porcentaje_compensacion(240, True) == Decimal("50.00")
    assert calcular_porcentaje_compensacion(359, True) == Decimal("50.00")
    assert calcular_porcentaje_compensacion(360, True) == Decimal("100.00")
    assert calcular_porcentaje_compensacion(600, True) == Decimal("100.00")


def test_ca03_causa_no_imputable_no_compensa():
    assert calcular_porcentaje_compensacion(600, False) == Decimal("0.00")


def test_ca03_cancelacion_imputable_con_aviso_menor_a_72h_compensa_100():
    assert calcular_porcentaje_compensacion(0, True, es_cancelacion=True, horas_aviso=71) == Decimal("100.00")
    assert calcular_porcentaje_compensacion(0, True, es_cancelacion=True, horas_aviso=72) == Decimal("0.00")


# ── CA-04 / RN-04: auditoría climática ────────────────────────────────────


def test_ca04_umbrales_de_clima_adverso():
    assert evaluar_condiciones_adversas(velocidad_viento_kmh=51) is True
    assert evaluar_condiciones_adversas(velocidad_viento_kmh=50) is False
    assert evaluar_condiciones_adversas(visibilidad_km=Decimal("0.99")) is True
    assert evaluar_condiciones_adversas(visibilidad_km=Decimal("1.00")) is False


def _clima(db, id_observacion, id_aeropuerto, fecha, viento=10, visibilidad=10):
    db.add(
        models.ObservacionClima(
            id_observacion_clima=id_observacion,
            id_aeropuerto=id_aeropuerto,
            fecha_hora_observacion_utc=fecha,
            fecha_hora_recepcion_utc=fecha,
            visibilidad_km=Decimal(str(visibilidad)),
            velocidad_viento_kmh=Decimal(str(viento)),
            codigo_clima="DESPEJADO",
        )
    )
    db.commit()


def test_ca04_causa_tecnica_con_clima_adverso_en_origen_requiere_auditoria(db):
    # El vuelo AC100 sale de MDE (aeropuerto 2) a las 13:00.
    _clima(db, 1, 2, SALIDA_AC100, visibilidad=Decimal("0.5"))

    resultado = procesar_evento_oooi(
        evento("OUT", 1, SALIDA_AC100 + timedelta(minutes=5), causa="TECNICA"), db
    )

    assert resultado == "ok"
    incidencia = db.query(models.IncidenciaVuelo).one()
    assert incidencia.requiere_auditoria is True

    auditoria = db.query(models.AuditoriaCausa).one()
    assert auditoria.id_incidencia == incidencia.id_incidencia
    assert auditoria.id_observacion_clima_origen == 1
    assert auditoria.id_observacion_clima_destino is None
    assert auditoria.estado == "PENDIENTE"


def test_ca04_causa_no_tecnica_no_requiere_auditoria(db):
    _clima(db, 1, 2, SALIDA_AC100, viento=80)

    procesar_evento_oooi(evento("OUT", 1, SALIDA_AC100 + timedelta(minutes=5), causa="CLIMA"), db)

    incidencia = db.query(models.IncidenciaVuelo).one()
    assert incidencia.requiere_auditoria is False
    assert db.query(models.AuditoriaCausa).count() == 0


def test_ca04_clima_fuera_de_la_ventana_de_una_hora_no_audita(db):
    _clima(db, 1, 2, SALIDA_AC100 + timedelta(hours=3), viento=80)

    procesar_evento_oooi(
        evento("OUT", 1, SALIDA_AC100 + timedelta(minutes=5), causa="TECNICA"), db
    )

    assert db.query(models.IncidenciaVuelo).one().requiere_auditoria is False
    assert db.query(models.AuditoriaCausa).count() == 0


def test_ca04_auditoria_climatica_consulta_origen_y_destino(db):
    _clima(db, 1, 3, utc(2026, 11, 5, 15), viento=75)  # destino MIA del vuelo AC200

    requiere, origen, destino = evaluar_auditoria_climatica(
        db, id_ruta=2, fecha_evento=utc(2026, 11, 5, 15), codigo_causa="TECNICA"
    )

    assert requiere is True
    assert origen is None
    assert destino == 1


# ── CA-05 / RN-08: propagación por matrícula ──────────────────────────────


def test_ca05_rotacion_nacional_e_internacional():
    assert minutos_rotacion("NACIONAL") == 45
    assert minutos_rotacion("INTERNACIONAL") == 60
    assert minutos_rotacion(None) == 45


def test_ca05_retraso_propagado_descuenta_la_rotacion():
    assert calcular_retraso_propagado(100, "NACIONAL") == 55
    assert calcular_retraso_propagado(100, "INTERNACIONAL") == 40
    assert calcular_retraso_propagado(30, "NACIONAL") == 0


# ── RN-03 y RN-09 ─────────────────────────────────────────────────────────


def test_rn03_clasificacion_de_causas():
    assert resolver_causa("tecnica") == (1, True, True)
    assert resolver_causa("CLIMA") == (4, False, True)
    assert resolver_causa("ERROR_99") == (None, False, False)


def test_rn09_clave_idempotente_por_evento_y_por_segmento():
    assert generar_clave_idempotencia(1, 1, 10) == generar_clave_idempotencia(1, 1, 10)
    assert generar_clave_idempotencia(1, 1, 10) != generar_clave_idempotencia(1, 1, 11)

    assert generar_clave_idempotencia_segmento(1, 1) == generar_clave_idempotencia_segmento(1, 1)
    assert generar_clave_idempotencia_segmento(1, 1) != generar_clave_idempotencia_segmento(2, 1)
