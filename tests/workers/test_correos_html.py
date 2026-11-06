"""Versión HTML de los correos."""

from datetime import datetime
from zoneinfo import ZoneInfo

from shared.notificaciones import VUELO_CANCELADO
from tests.workers.conftest import EnviadorFalso, utc
from worker_notificaciones import plantillas
from worker_notificaciones.consultas import InfoVuelo
from worker_notificaciones.correo import EnviadorGmail
from worker_notificaciones.procesador import procesar_mensaje

BOGOTA = ZoneInfo("America/Bogota")
NUEVA_YORK = ZoneInfo("America/New_York")

VUELO = InfoVuelo("AC100", "MDE", "BOG", datetime(2026, 11, 5, 8, 0, tzinfo=BOGOTA),
                  datetime(2026, 11, 5, 9, 30, tzinfo=BOGOTA), "José María Córdova", "El Dorado")
# Sale de Bogotá a las 10:00 (hora de Bogotá) y llega a Miami a las 15:00 (hora de Miami): 4 h de vuelo.
OTRO_VUELO = InfoVuelo("AC200", "BOG", "MIA", datetime(2026, 11, 5, 10, 0, tzinfo=BOGOTA),
                       datetime(2026, 11, 5, 15, 0, tzinfo=NUEVA_YORK))

MENSAJE_CANCELADO = {
    "id_vuelo": 1,
    "fecha_evento_utc": utc(2026, 11, 5, 13).isoformat(),
    "codigo_causa": "TECNICA",
    "es_imputable": True,
}


def test_todas_las_plantillas_generan_html_y_texto():
    correos = [
        plantillas.vuelo_cancelado("Ana", VUELO, True),
        plantillas.vuelo_retrasado("Ana", VUELO, 130, False),
        plantillas.conexion_en_riesgo("Ana", VUELO, OTRO_VUELO, "BOG", 30, 50, perdida=False),
        plantillas.conexion_en_riesgo("Ana", VUELO, OTRO_VUELO, "BOG", -70, 50, perdida=True),
        plantillas.itinerario_cambiado("Ana", VUELO, OTRO_VUELO, 7),
    ]
    for correo in correos:
        assert correo.html.startswith("<!DOCTYPE html>")
        assert "Hola, Ana" in correo.html
        assert "Información operativa" in correo.html
        assert correo.texto.startswith("Hola Ana,")


def test_tarjeta_muestra_horas_ruta_fecha_y_duracion():
    tarjeta = plantillas.tarjeta_vuelo(VUELO, "Nuevo itinerario", plantillas.VERDE)

    assert "AC100" in tarjeta
    assert "jue. 05 nov. 2026" in tarjeta
    assert "08:00" in tarjeta and "09:30" in tarjeta
    assert "MDE" in tarjeta and "BOG" in tarjeta
    assert "1h 30m" in tarjeta
    assert "line-through" not in tarjeta


def test_duracion_tiene_en_cuenta_las_zonas_horarias():
    # Sale de Bogotá a las 10:00 (15:00 UTC) y llega a Madrid a las 05:00 del día siguiente (04:00 UTC).
    # Restando "a ojo" darían 19 h, pero el vuelo dura 13 h.
    vuelo = InfoVuelo("AC900", "BOG", "MAD", datetime(2026, 11, 5, 10, 0, tzinfo=BOGOTA),
                      datetime(2026, 11, 6, 5, 0, tzinfo=ZoneInfo("Europe/Madrid")))
    assert plantillas.duracion_vuelo(vuelo) == "13h 0m"


def test_cambio_de_itinerario_muestra_nuevo_y_anterior_tachado():
    correo = plantillas.itinerario_cambiado("Ana", VUELO, OTRO_VUELO, 7)

    assert "Nuevo itinerario" in correo.html
    assert "Anterior itinerario" in correo.html
    assert correo.html.count("line-through") == 2  # solo las 2 horas del vuelo anterior
    assert correo.html.index("AC200") < correo.html.index("Anterior itinerario")  # primero el nuevo


def test_retraso_muestra_la_hora_nueva():
    correo = plantillas.vuelo_retrasado("Ana", VUELO, 130, False)

    assert "ahora sale desde José María Córdova (MDE) a las 10:10" in correo.html
    assert "llegando a las 11:40" in correo.html
    assert "Nueva hora" in correo.html and "Hora anterior" in correo.html


def test_cancelacion_tiene_etiqueta_roja_y_horas_tachadas():
    correo = plantillas.vuelo_cancelado("Ana", VUELO, True)

    assert "Cancelado" in correo.html
    assert plantillas.ROJO in correo.html
    assert "line-through" in correo.html
    assert "tienes derecho a una compensación" in correo.html


def test_nombres_con_html_se_muestran_como_texto():
    correo = plantillas.vuelo_cancelado("<script>alert(1)</script>", VUELO, True)

    assert "<script>" not in correo.html
    assert "&lt;script&gt;" in correo.html


def test_correo_enviado_lleva_html_sin_la_marca_interna(db):
    enviador = EnviadorFalso()
    procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, enviador)

    html = enviador.enviados[0]["html"]
    assert "AC100" in html
    assert plantillas.MARCA_MODO_PRUEBAS not in html
    assert "MODO PRUEBAS" not in html


def test_modo_pruebas_muestra_aviso_dentro_del_html(db, monkeypatch):
    monkeypatch.setenv("EMAIL_DESTINO_PRUEBAS", "equipo@vueladata.test")
    enviador = EnviadorFalso()
    procesar_mensaje(db, VUELO_CANCELADO, MENSAJE_CANCELADO, enviador)

    assert "MODO PRUEBAS</strong> · Este correo era para: ana@example.com" in enviador.enviados[0]["html"]


def test_el_mensaje_lleva_texto_y_html():
    correo = plantillas.vuelo_cancelado("Ana", VUELO, True)

    mensaje = EnviadorGmail().armar_mensaje("ana@example.com", correo.asunto, correo.texto, correo.html)

    assert mensaje.get_content_type() == "multipart/alternative"
    tipos = [parte.get_content_type() for parte in mensaje.iter_parts()]
    assert tipos == ["text/plain", "text/html"]
