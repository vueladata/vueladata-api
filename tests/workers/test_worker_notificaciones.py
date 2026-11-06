"""worker_notificaciones: qué correos envía y cómo los registra en la tabla notificacion."""

from datetime import timedelta

from shared import models
from shared.notificaciones import CONEXION_EN_RIESGO, ITINERARIO_CAMBIADO, VUELO_CANCELADO, VUELO_RETRASADO
from tests.workers.conftest import EnviadorFalso, evento, utc
from worker_notificaciones.procesador import procesar_mensaje
from worker_rds.handlers.oooi_handler import procesar_evento_oooi

SALIDA_AC100 = utc(2026, 11, 5, 13)

MENSAJE_CANCELADO = {
    "id_vuelo": 1,
    "fecha_evento_utc": SALIDA_AC100.isoformat(),
    "codigo_causa": "TECNICA",
    "es_imputable": True,
}


def test_cancelacion_envia_correo_a_cada_pasajero(db):
    enviador = EnviadorFalso()

    resumen = procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, enviador)

    # Ana recibe el correo; Beto no tiene correo -> queda FALLIDA.
    assert resumen == {"enviados": 1, "omitidos": 0, "fallidos": 1}
    correo = enviador.enviados[0]
    assert correo["para"] == "ana@example.com"
    assert correo["asunto"] == "Tu vuelo AC100 fue cancelado"
    # RN-02: sale 13:00 UTC = 08:00 hora local de Medellín.
    assert "del jue. 05 nov. 2026, que salía desde José María Córdova (MDE) a las 08:00" in correo["cuerpo"]
    assert "tienes derecho a una compensación" in correo["cuerpo"]  # RN-05: causa imputable

    estados = {n.id_detalle_reserva: n.estado_envio for n in db.query(models.Notificacion).all()}
    assert estados == {1: "ENVIADA", 3: "FALLIDA"}


def test_mensaje_repetido_no_envia_dos_veces(db):
    enviador = EnviadorFalso()
    procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, enviador)
    segundo = procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, enviador)

    assert segundo["omitidos"] == 1
    assert len(enviador.enviados) == 1
    assert db.query(models.Notificacion).count() == 2  # no se crean filas nuevas


def test_si_gmail_falla_queda_fallida_y_se_reintenta(db):
    procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, EnviadorFalso(fallar=True))
    ana = db.query(models.Notificacion).filter_by(id_detalle_reserva=1).one()
    assert ana.estado_envio == "FALLIDA"

    # RabbitMQ vuelve a entregar el mensaje y ahora Gmail sí responde.
    enviador = EnviadorFalso()
    procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, enviador)
    db.refresh(ana)
    assert ana.estado_envio == "ENVIADA"
    assert ana.fecha_envio_utc is not None
    assert len(enviador.enviados) == 1


def test_modo_pruebas_manda_todo_a_un_solo_correo(db, monkeypatch):
    monkeypatch.setenv("EMAIL_DESTINO_PRUEBAS", "equipo@vueladata.test")
    enviador = EnviadorFalso()

    resumen = procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, enviador)

    assert resumen["enviados"] == 2  # también el de Beto, aunque no tenga correo
    assert {c["para"] for c in enviador.enviados} == {"equipo@vueladata.test"}
    assert "Este correo era para: ana@example.com" in enviador.enviados[0]["cuerpo"]


def test_retraso_por_clima_explica_que_no_hay_compensacion(db):
    enviador = EnviadorFalso()
    mensaje = {"id_vuelo": 1, "fecha_evento_utc": SALIDA_AC100.isoformat(), "minutos_retraso": 150,
               "codigo_causa": "CLIMA", "es_imputable": False}

    procesar_mensaje(db, VUELO_RETRASADO, mensaje, enviador)

    correo = enviador.enviados[0]
    assert correo["asunto"] == "Tu vuelo AC100 tiene un retraso de 2 h 30 min"
    assert "no genera compensación económica" in correo["cuerpo"]  # RN-06
    assert "derecho a reprogramar" in correo["cuerpo"]


def test_flujo_completo_conexion_en_riesgo(db, publicar, publicados):
    # worker_rds recibe el OUT con 30 min de retraso y publica conexion.en_riesgo...
    procesar_evento_oooi(evento("OUT", 1, SALIDA_AC100 + timedelta(minutes=30), causa="TECNICA"), db, publicar)
    routing_key, datos = publicados[0]
    assert routing_key == CONEXION_EN_RIESGO

    # ...y worker_notificaciones lo convierte en un correo.
    enviador = EnviadorFalso()
    procesar_mensaje(db, routing_key, datos, enviador)

    assert enviador.enviados[0]["asunto"] == "Tu conexión en BOG está en riesgo"
    assert "solo tendrás 30 minutos" in enviador.enviados[0]["cuerpo"]
    notificacion = db.query(models.Notificacion).one()
    assert notificacion.tipo == "CONEXION_RIESGO"
    assert notificacion.id_evaluacion_conexion == datos["id_evaluacion"]


def test_flujo_completo_cancelacion_y_nuevo_itinerario(db, publicar, publicados):
    procesar_evento_oooi(evento("CANCEL", 1, SALIDA_AC100, causa="TECNICA"), db, publicar)
    enviador = EnviadorFalso()

    for routing_key, datos in publicados:
        procesar_mensaje(db, routing_key, datos, enviador)

    asuntos = [c["asunto"] for c in enviador.enviados]
    # Ana recibe 2 correos: la cancelación y la propuesta de nuevo vuelo. Beto no tiene correo.
    assert asuntos == ["Tu vuelo AC100 fue cancelado", "Te ofrecemos un nuevo vuelo: AC102"]
    assert "PATCH /me/reubicaciones/1" in enviador.enviados[1]["cuerpo"]
    tipos = sorted(n.tipo for n in db.query(models.Notificacion).filter_by(id_detalle_reserva=1))
    assert tipos == ["INTERRUPCION", "REUBICACION"]


def test_itinerario_de_reubicacion_inexistente_no_envia_nada(db):
    enviador = EnviadorFalso()

    resumen = procesar_mensaje(db, ITINERARIO_CAMBIADO, {"id_reubicacion": 999}, enviador)

    assert resumen == {"enviados": 0, "omitidos": 0, "fallidos": 0}


def test_routing_key_desconocida_se_ignora(db):
    resumen = procesar_mensaje(db, "algo.raro", {}, EnviadorFalso())

    assert resumen == {"enviados": 0, "omitidos": 0, "fallidos": 0}
