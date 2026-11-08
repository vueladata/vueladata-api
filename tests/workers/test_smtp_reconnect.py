"""worker_notificaciones: reconexión SMTP cuando Gmail cierra la conexión."""

import smtplib

from worker_notificaciones.correo import EnviadorGmail


class SMTPFalso:
    """Primera conexión: Gmail la cerró por inactividad. Segunda: funciona."""

    instancias = []

    def __init__(self, host, puerto, timeout=20):
        self.host = host
        self.puerto = puerto
        self.mensajes = []
        self.fallar_una_vez = len(SMTPFalso.instancias) == 0
        SMTPFalso.instancias.append(self)

    def starttls(self):
        return None

    def login(self, usuario, clave):
        return None

    def send_message(self, mensaje):
        if self.fallar_una_vez:
            self.fallar_una_vez = False
            raise smtplib.SMTPServerDisconnected("Gmail cerró la conexión inactiva")
        self.mensajes.append(mensaje)

    def quit(self):
        return None


def test_enviador_se_reconecta_una_vez_tras_desconexion_smtp(monkeypatch):
    SMTPFalso.instancias = []
    monkeypatch.setattr(smtplib, "SMTP", SMTPFalso)
    monkeypatch.setenv("SMTP_USUARIO", "cuenta@vueladata.test")
    monkeypatch.setenv("SMTP_CLAVE", "clave-de-aplicacion")

    enviador = EnviadorGmail()
    enviador.enviar("ana@example.com", "Asunto", "Cuerpo")

    assert len(SMTPFalso.instancias) == 2
    assert SMTPFalso.instancias[0].mensajes == []
    assert len(SMTPFalso.instancias[1].mensajes) == 1
    assert SMTPFalso.instancias[1].mensajes[0]["To"] == "ana@example.com"


def test_cerrar_libera_la_conexion(monkeypatch):
    SMTPFalso.instancias = []
    monkeypatch.setattr(smtplib, "SMTP", SMTPFalso)
    monkeypatch.setenv("SMTP_USUARIO", "cuenta@vueladata.test")
    monkeypatch.setenv("SMTP_CLAVE", "clave-de-aplicacion")

    enviador = EnviadorGmail()
    enviador.enviar("ana@example.com", "Asunto", "Cuerpo")
    enviador.cerrar()

    assert enviador.servidor is None
