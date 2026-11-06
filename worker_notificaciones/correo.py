import os
import smtplib
from email.message import EmailMessage


class EnviadorGmail:
    """Envía correos por SMTP (Gmail).

    Mantiene una sola conexión abierta para no iniciar sesión en Gmail por cada correo,
    y se reconecta una vez si Gmail cerró la conexión por inactividad.

    Variables de entorno:
      SMTP_HOST (smtp.gmail.com), SMTP_PORT (587), SMTP_USUARIO (tu cuenta de Gmail),
      SMTP_CLAVE (contraseña de aplicación de Google, NO tu contraseña normal),
      SMTP_REMITENTE (opcional, por defecto SMTP_USUARIO).
    """

    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.puerto = int(os.getenv("SMTP_PORT", "587"))
        self.usuario = os.getenv("SMTP_USUARIO", "")
        self.clave = os.getenv("SMTP_CLAVE", "")
        self.remitente = os.getenv("SMTP_REMITENTE") or self.usuario
        self.servidor = None

    def esta_configurado(self) -> bool:
        return bool(self.usuario and self.clave)

    def _conectar(self) -> None:
        servidor = smtplib.SMTP(self.host, self.puerto, timeout=20)
        servidor.starttls()  # cifra la conexión antes de enviar usuario y clave
        servidor.login(self.usuario, self.clave)
        self.servidor = servidor

    def armar_mensaje(self, destinatario: str, asunto: str, texto: str, html: str | None = None) -> EmailMessage:
        """Arma un correo "multipart/alternative": lleva el texto plano y el HTML.

        El programa de correo del pasajero muestra el HTML; si no puede, muestra el texto.
        """
        mensaje = EmailMessage()
        mensaje["From"] = self.remitente
        mensaje["To"] = destinatario
        mensaje["Subject"] = asunto
        mensaje.set_content(texto)
        if html:
            mensaje.add_alternative(html, subtype="html")
        return mensaje

    def enviar(self, destinatario: str, asunto: str, texto: str, html: str | None = None) -> None:
        mensaje = self.armar_mensaje(destinatario, asunto, texto, html)

        if self.servidor is None:
            self._conectar()
        try:
            self.servidor.send_message(mensaje)
        except smtplib.SMTPServerDisconnected:
            # Gmail cierra conexiones inactivas: reconectamos y reintentamos una vez.
            self._conectar()
            self.servidor.send_message(mensaje)

    def cerrar(self) -> None:
        if self.servidor is not None:
            try:
                self.servidor.quit()
            except smtplib.SMTPException:
                pass
            self.servidor = None
