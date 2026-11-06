"""worker_rds: qué notificaciones publica en RabbitMQ según el evento que recibe."""

from datetime import timedelta

from shared import models
from shared.notificaciones import CONEXION_EN_RIESGO, ITINERARIO_CAMBIADO, VUELO_CANCELADO, VUELO_RETRASADO
from tests.workers.conftest import evento, utc
from worker_rds.handlers.oooi_handler import procesar_evento_oooi

SALIDA_AC100 = utc(2026, 11, 5, 13)


def llaves(publicados):
    return [routing_key for routing_key, _datos in publicados]


def test_cancelacion_marca_el_vuelo_ofrece_reubicacion_y_publica(db, publicar, publicados):
    resultado = procesar_evento_oooi(evento("CANCEL", 1, SALIDA_AC100, causa="TECNICA"), db, publicar=publicar)

    assert resultado == "ok"
    assert db.query(models.Vuelo).filter_by(id_vuelo=1).one().id_estado_vuelo_actual == 9  # CANCELADO
    assert db.query(models.IncidenciaVuelo).one().tipo == "CANCELACION"

    reubicaciones = db.query(models.Reubicacion).all()
    assert len(reubicaciones) == 2  # Ana y Beto
    assert {r.estado for r in reubicaciones} == {"OFRECIDA"}
    assert {r.id_vuelo_propuesto for r in reubicaciones} == {3}  # AC102, misma ruta y más tarde

    assert llaves(publicados) == [VUELO_CANCELADO, ITINERARIO_CAMBIADO, ITINERARIO_CAMBIADO]
    assert publicados[0][1]["es_imputable"] is True


def test_evento_repetido_no_vuelve_a_notificar(db, publicar, publicados):
    mensaje = evento("CANCEL", 1, SALIDA_AC100, causa="TECNICA")
    procesar_evento_oooi(mensaje, db, publicar=publicar)
    segundo = procesar_evento_oooi(mensaje, db, publicar=publicar)

    assert segundo == "duplicado"
    assert len(publicados) == 3  # solo las del primer procesamiento


def test_retraso_grande_avisa_retraso_y_conexion_perdida(db, publicar, publicados):
    # 130 min tarde: llega 16:10, pero AC200 sale 15:00 -> conexión PERDIDA.
    procesar_evento_oooi(evento("OUT", 1, SALIDA_AC100 + timedelta(minutes=130), causa="TECNICA"), db, publicar)

    assert llaves(publicados) == [VUELO_RETRASADO, CONEXION_EN_RIESGO]
    assert publicados[0][1]["minutos_retraso"] == 130
    assert db.query(models.EvaluacionConexion).one().estado == "PERDIDA"


def test_retraso_pequeno_solo_avisa_si_pone_en_riesgo_la_conexion(db, publicar, publicados):
    # 30 min tarde: quedan 30 min para conectar y el mínimo es 50 -> EN_RIESGO (RN-07).
    # 30 min no alcanza el umbral de 120 para avisar del retraso en sí.
    procesar_evento_oooi(evento("OUT", 1, SALIDA_AC100 + timedelta(minutes=30), causa="TECNICA"), db, publicar)

    assert llaves(publicados) == [CONEXION_EN_RIESGO]
    evaluacion = db.query(models.EvaluacionConexion).one()
    assert (evaluacion.estado, evaluacion.minutos_disponibles, evaluacion.minutos_requeridos) == ("EN_RIESGO", 30, 50)


def test_retraso_que_no_afecta_la_conexion_no_publica_nada(db, publicar, publicados):
    procesar_evento_oooi(evento("OUT", 1, SALIDA_AC100 + timedelta(minutes=5), causa="TECNICA"), db, publicar)

    assert publicados == []
    assert db.query(models.EvaluacionConexion).one().estado == "NORMAL"  # igual queda registrada


def test_si_falla_rabbitmq_el_evento_igual_queda_guardado(db):
    def publicar_que_falla(routing_key, datos):
        raise ConnectionError("RabbitMQ caído")

    resultado = procesar_evento_oooi(evento("CANCEL", 1, SALIDA_AC100, causa="TECNICA"), db, publicar_que_falla)

    assert resultado == "ok"
    assert db.query(models.EventoOperacional).count() == 1


def test_sin_publicar_funciona_como_antes(db):
    # worker_rds sin la función publicar (por ejemplo, en otros scripts) sigue procesando el evento.
    assert procesar_evento_oooi(evento("OUT", 1, SALIDA_AC100, causa=None), db) == "ok"
