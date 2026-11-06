"""Textos de los correos.

Cada función devuelve un Correo con dos versiones del mismo mensaje:
- html: la versión bonita, la que ve el pasajero en Gmail, Outlook, etc.
- texto: versión de respaldo para programas que no muestran HTML.

Diseño del HTML (de arriba a abajo):
  1. Cabecera blanca con el logo y "Información operativa".
  2. "Hola, <nombre>" y un párrafo que explica qué pasó.
  3. Una o dos tarjetas de vuelo: número, fecha, horas grandes, ruta y duración.
     La etiqueta de color de la esquina dice qué es (Nuevo itinerario, Cancelado...).
     El horario que ya no vale se muestra en gris y tachado.
  4. Puntos con los derechos del pasajero y qué hacer.
  5. Firma y pie.

Sobre el HTML de correos:
- Los programas de correo ignoran casi todo el CSS de <style>, por eso los estilos van
  en cada etiqueta (style="...") y el diseño se arma con tablas.
- Todo dato que viene de la base (nombres, códigos) pasa por escape() para que, si alguien
  tiene un nombre como "<script>", se muestre como texto y no se ejecute.
"""

from dataclasses import dataclass
from datetime import datetime
from html import escape

from worker_notificaciones.consultas import InfoVuelo

AEROLINEA = "Aerovía Continental"

# Colores
AZUL_MARCA = "#0b3d91"  # logo
TURQUESA = "#0d9488"  # puntos de la línea de vuelo
VERDE = "#16a34a"  # etiqueta "Nuevo itinerario" / "Nueva hora"
NARANJA = "#ea580c"  # etiqueta "Anterior itinerario" / "Retrasado" y línea del pie
AMBAR = "#d97706"  # etiqueta "Conexión en riesgo"
ROJO = "#dc2626"  # etiqueta "Cancelado" / "Conexión perdida"

# worker_notificaciones reemplaza esta marca por un aviso cuando está en modo pruebas.
MARCA_MODO_PRUEBAS = "<!--AVISO_MODO_PRUEBAS-->"

CONSULTA_ESTADO = (
    "Consulta el estado de tu vuelo en la API de pasajeros de VuelaData con tu código de reserva "
    "y tu número de documento."
)

DIAS = ["lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom."]
MESES = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sep.", "oct.", "nov.", "dic."]


@dataclass
class Correo:
    asunto: str
    texto: str
    html: str


# ── Formatos ────────────────────────────────────────────────────────────────


def fecha_corta(fecha: datetime) -> str:
    """Ej. 'jue. 05 nov. 2026' (sin depender del idioma del sistema operativo)."""
    return f"{DIAS[fecha.weekday()]} {fecha.day:02d} {MESES[fecha.month - 1]} {fecha.year}"


def hora(fecha: datetime) -> str:
    return fecha.strftime("%H:%M")


def duracion_vuelo(vuelo: InfoVuelo) -> str:
    """Ej. '1h 30m'. Las dos horas tienen su zona horaria, así que la resta es correcta."""
    horas, minutos = divmod(int((vuelo.llegada - vuelo.salida).total_seconds() // 60), 60)
    return f"{horas}h {minutos}m"


def duracion_retraso(minutos: int) -> str:
    horas, minutos = divmod(minutos, 60)
    return f"{horas} h {minutos} min"


def lugar(codigo: str, nombre: str) -> str:
    """Ej. 'El Dorado (BOG)'; si no conocemos el nombre, solo 'BOG'."""
    return f"{nombre} ({codigo})" if nombre else codigo


def texto_derechos(es_imputable: bool) -> str:
    """RN-05 / RN-06: qué derechos tiene el pasajero según la causa."""
    if es_imputable:
        return (
            "La causa es responsabilidad de la aerolínea, así que tienes derecho a una compensación "
            "económica. La calcularemos automáticamente en las próximas 24 horas."
        )
    return (
        "La causa no es responsabilidad de la aerolínea (por ejemplo clima o control de tráfico aéreo), "
        "por lo que no genera compensación económica, pero sí tienes derecho a reprogramar tu vuelo."
    )


# ── Piezas del HTML ─────────────────────────────────────────────────────────


def tarjeta_vuelo(vuelo: InfoVuelo, etiqueta: str, color: str, anterior: bool = False) -> str:
    """Tarjeta de un vuelo. anterior=True: fondo gris y horas tachadas (el horario que ya no vale)."""
    fondo = "#f1f5f9" if anterior else "#ffffff"
    tachado = "text-decoration:line-through;" if anterior else ""
    estilo_hora = f"font-size:28px;font-weight:bold;color:#0f172a;{tachado}"
    estilo_codigo = "padding-top:2px;font-size:14px;color:#334155;"
    linea = '<div style="border-top:1px dotted #94a3b8;height:1px;font-size:0;line-height:0;"></div>'

    return f"""
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="margin:0 0 20px;background:{fondo};border:1px solid #e2e8f0;border-radius:12px;">
            <tr><td style="padding:18px 20px 4px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td valign="top">
                  <span style="font-size:22px;font-weight:bold;color:#0f172a;">&#9992;&#xFE0E; {escape(vuelo.numero_vuelo)}</span>
                  <span style="font-size:12px;color:#334155;">&nbsp; {fecha_corta(vuelo.salida)}</span>
                  <div style="margin-top:2px;font-size:12px;color:#64748b;">Operado por {AEROLINEA}</div>
                </td>
                <td valign="top" align="right">
                  <span style="display:inline-block;padding:4px 10px;border:1px solid {color};border-radius:6px;
                               background:#ffffff;font-size:12px;font-weight:bold;color:{color};white-space:nowrap;">{escape(etiqueta)}</span>
                </td>
              </tr></table>
            </td></tr>
            <tr><td style="padding:10px 20px 18px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="80" style="{estilo_hora}">{hora(vuelo.salida)}</td>
                  <td>
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                      <td width="10" style="font-size:10px;color:{TURQUESA};">&#9679;</td>
                      <td>{linea}</td>
                      <td width="24" align="center" style="font-size:15px;color:#0f172a;">&#9992;&#xFE0E;</td>
                      <td>{linea}</td>
                      <td width="10" align="right" style="font-size:10px;color:{TURQUESA};">&#9679;</td>
                    </tr></table>
                  </td>
                  <td width="80" align="right" style="{estilo_hora}">{hora(vuelo.llegada)}</td>
                </tr>
                <tr>
                  <td style="{estilo_codigo}">{escape(vuelo.origen)}</td>
                  <td align="center" style="{estilo_codigo}">{duracion_vuelo(vuelo)}</td>
                  <td align="right" style="{estilo_codigo}">{escape(vuelo.destino)}</td>
                </tr>
              </table>
            </td></tr>
          </table>"""


def armar_html(titulo: str, nombre: str, mensaje: str, tarjetas: list[str], puntos: list[str]) -> str:
    """Arma el correo completo.

    titulo: título de la pestaña / vista previa. mensaje: párrafo que explica qué pasó.
    tarjetas: HTML de tarjeta_vuelo(). puntos: frases que se muestran con viñeta al final.
    """
    html_puntos = "".join(
        f'<p style="margin:0 0 14px;font-size:14px;line-height:1.6;color:#334155;">&bull; {escape(p)}</p>'
        for p in puntos
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(titulo)}</title></head>
<body style="margin:0;padding:0;background:#e2e8f0;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#f8fafc;">

        <tr><td style="background:#ffffff;padding:22px 28px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="padding-right:14px;font-size:22px;font-weight:bold;color:{AZUL_MARCA};">aerovía &#9992;&#xFE0E;</td>
            <td style="padding-left:14px;border-left:1px solid #cbd5e1;font-size:13px;font-weight:bold;color:#64748b;">Información operativa</td>
          </tr></table>
        </td></tr>

        <tr><td style="padding:28px 28px 8px;">
          {MARCA_MODO_PRUEBAS}
          <p style="margin:0 0 16px;font-size:20px;font-weight:bold;color:#0f172a;text-align:center;">Hola, {escape(nombre)}</p>
          <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#334155;text-align:justify;">{escape(mensaje)}</p>
          {"".join(tarjetas)}
          {html_puntos}
          <p style="margin:28px 0 20px;font-size:17px;font-weight:bold;color:#0f172a;text-align:center;">Equipo {AEROLINEA}</p>
        </td></tr>

        <tr><td style="padding:16px 28px 24px;border-top:2px solid {NARANJA};font-size:12px;line-height:1.6;color:#94a3b8;text-align:center;">
          Este es un correo automático, por favor no lo respondas.<br>Las horas están en la hora local de cada aeropuerto.
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def armar_texto(nombre: str, mensaje: str, puntos: list[str]) -> str:
    """Versión en texto plano: el mismo mensaje y los mismos puntos."""
    lista = "\n".join(f"- {p}" for p in puntos)
    return f"Hola {nombre},\n\n{mensaje}\n\n{lista}\n\nEquipo {AEROLINEA}"


# ── Un correo por cada situación ────────────────────────────────────────────


def vuelo_cancelado(nombre: str, vuelo: InfoVuelo, es_imputable: bool) -> Correo:
    asunto = f"Tu vuelo {vuelo.numero_vuelo} fue cancelado"
    mensaje = (
        f"Lamentamos informarte que tu vuelo {vuelo.numero_vuelo} del {fecha_corta(vuelo.salida)}, que salía desde "
        f"{lugar(vuelo.origen, vuelo.origen_nombre)} a las {hora(vuelo.salida)} con destino a "
        f"{lugar(vuelo.destino, vuelo.destino_nombre)}, fue cancelado."
    )
    puntos = [
        texto_derechos(es_imputable),
        "Si hay un vuelo alternativo te enviaremos otro correo con la propuesta de reubicación.",
        CONSULTA_ESTADO,
    ]
    tarjetas = [tarjeta_vuelo(vuelo, "Cancelado", ROJO, anterior=True)]
    return Correo(asunto, armar_texto(nombre, mensaje, puntos), armar_html(asunto, nombre, mensaje, tarjetas, puntos))


def vuelo_retrasado(nombre: str, vuelo: InfoVuelo, minutos_retraso: int, es_imputable: bool) -> Correo:
    retraso = duracion_retraso(minutos_retraso)
    nuevo = vuelo.con_retraso(minutos_retraso)
    asunto = f"Tu vuelo {vuelo.numero_vuelo} tiene un retraso de {retraso}"
    mensaje = (
        f"Hubo un cambio en tu vuelo {vuelo.numero_vuelo} del {fecha_corta(vuelo.salida)}. Por un retraso de "
        f"{retraso}, ahora sale desde {lugar(vuelo.origen, vuelo.origen_nombre)} a las {hora(nuevo.salida)} "
        f"con destino a {lugar(vuelo.destino, vuelo.destino_nombre)}, llegando a las {hora(nuevo.llegada)}."
    )
    puntos = [texto_derechos(es_imputable), CONSULTA_ESTADO]
    tarjetas = [
        tarjeta_vuelo(nuevo, "Nueva hora", VERDE),
        tarjeta_vuelo(vuelo, "Hora anterior", NARANJA, anterior=True),
    ]
    return Correo(asunto, armar_texto(nombre, mensaje, puntos), armar_html(asunto, nombre, mensaje, tarjetas, puntos))


def conexion_en_riesgo(
    nombre: str,
    vuelo_llegada: InfoVuelo,
    vuelo_salida: InfoVuelo,
    aeropuerto: str,
    minutos_disponibles: int,
    minutos_requeridos: int,
    perdida: bool,
    minutos_retraso: int = 0,
) -> Correo:
    """minutos_retraso: cuánto se retrasa vuelo_llegada (para mostrar su nueva hora en la tarjeta)."""
    if perdida:
        asunto = f"Perdiste tu conexión en {aeropuerto}"
        etiqueta, color = "Conexión perdida", ROJO
        mensaje = (
            f"Por el retraso de tu vuelo {vuelo_llegada.numero_vuelo}, llegarás a {aeropuerto} después de que salga "
            f"tu vuelo de conexión {vuelo_salida.numero_vuelo} a {vuelo_salida.destino} "
            f"(salida a las {hora(vuelo_salida.salida)})."
        )
    else:
        asunto = f"Tu conexión en {aeropuerto} está en riesgo"
        etiqueta, color = "Conexión en riesgo", AMBAR
        mensaje = (
            f"Por el retraso de tu vuelo {vuelo_llegada.numero_vuelo}, solo tendrás {minutos_disponibles} minutos "
            f"para hacer tu conexión en {aeropuerto}, y el mínimo necesario es {minutos_requeridos} minutos. "
            f"Está en riesgo tu vuelo {vuelo_salida.numero_vuelo} a {vuelo_salida.destino} "
            f"(salida a las {hora(vuelo_salida.salida)})."
        )
    puntos = [
        "Nuestro equipo está buscando una alternativa para ti y te avisaremos si cambia tu itinerario.",
        CONSULTA_ESTADO,
    ]
    tarjetas = [
        tarjeta_vuelo(vuelo_llegada.con_retraso(minutos_retraso), "Retrasado", NARANJA),
        tarjeta_vuelo(vuelo_salida, etiqueta, color),
    ]
    return Correo(asunto, armar_texto(nombre, mensaje, puntos), armar_html(asunto, nombre, mensaje, tarjetas, puntos))


def itinerario_cambiado(
    nombre: str, vuelo_original: InfoVuelo, vuelo_propuesto: InfoVuelo, id_reubicacion: int
) -> Correo:
    asunto = f"Te ofrecemos un nuevo vuelo: {vuelo_propuesto.numero_vuelo}"
    mensaje = (
        f"Hubo un cambio en tu itinerario. Por la cancelación de tu vuelo {vuelo_original.numero_vuelo}, te "
        f"ofrecemos el vuelo {vuelo_propuesto.numero_vuelo} del {fecha_corta(vuelo_propuesto.salida)}, que sale "
        f"desde {lugar(vuelo_propuesto.origen, vuelo_propuesto.origen_nombre)} a las {hora(vuelo_propuesto.salida)} "
        f"con destino a {lugar(vuelo_propuesto.destino, vuelo_propuesto.destino_nombre)}, llegando a las "
        f"{hora(vuelo_propuesto.llegada)}."
    )
    puntos = [
        "Puedes aceptar o rechazar esta propuesta desde la API de pasajeros "
        f"(PATCH /me/reubicaciones/{id_reubicacion}).",
        CONSULTA_ESTADO,
    ]
    tarjetas = [
        tarjeta_vuelo(vuelo_propuesto, "Nuevo itinerario", VERDE),
        tarjeta_vuelo(vuelo_original, "Anterior itinerario", NARANJA, anterior=True),
    ]
    return Correo(asunto, armar_texto(nombre, mensaje, puntos), armar_html(asunto, nombre, mensaje, tarjetas, puntos))
