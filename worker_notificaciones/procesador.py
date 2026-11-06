"""Convierte un mensaje de RabbitMQ en correos a los pasajeros afectados."""

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape

from sqlalchemy.orm import Session

from shared.models.aeropuerto import Aeropuerto
from shared.models.conexion_itinerario import ConexionItinerario
from shared.models.evaluacion_conexion import EvaluacionConexion
from shared.models.notificacion import Notificacion
from shared.models.reubicacion import Reubicacion
from shared.models.tiempo_minimo_conexion import TiempoMinimoConexion
from shared.notificaciones import CONEXION_EN_RIESGO, ITINERARIO_CAMBIADO, VUELO_CANCELADO, VUELO_RETRASADO
from worker_notificaciones import plantillas
from worker_notificaciones.consultas import describir_vuelo, en_utc, pasajero_del_tramo, pasajeros_del_vuelo


@dataclass
class Aviso:
    """Un correo para un pasajero, más los datos para registrarlo en la tabla notificacion."""

    id_detalle_reserva: int
    correo: str | None
    tipo: str  # valor de notificacion.tipo: INTERRUPCION, CONEXION_RIESGO o REUBICACION
    fecha_evento: datetime  # junto con el tramo y el tipo, identifica la notificación (evita duplicados)
    asunto: str
    cuerpo: str  # versión en texto plano
    html: str  # versión con estilo (la que ve el pasajero)
    id_evaluacion_conexion: int | None = None


def leer_fecha(texto: str) -> datetime:
    fecha = datetime.fromisoformat(texto)
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha


# ── 1. Del mensaje a la lista de correos ──────────────────────────────────


def armar_avisos(db: Session, routing_key: str, datos: dict) -> list[Aviso]:
    if routing_key == VUELO_CANCELADO:
        return avisos_vuelo_cancelado(db, datos)
    if routing_key == VUELO_RETRASADO:
        return avisos_vuelo_retrasado(db, datos)
    if routing_key == CONEXION_EN_RIESGO:
        return avisos_conexion_en_riesgo(db, datos)
    if routing_key == ITINERARIO_CAMBIADO:
        return avisos_itinerario_cambiado(db, datos)
    print(f"[Worker Notificaciones] ⚠️ Routing key desconocida: {routing_key}. Se ignora.", flush=True)
    return []


def avisos_vuelo_cancelado(db: Session, datos: dict) -> list[Aviso]:
    vuelo = describir_vuelo(db, datos["id_vuelo"])
    if vuelo is None:
        return []
    avisos = []
    for tramo, pasajero in pasajeros_del_vuelo(db, datos["id_vuelo"]):
        correo = plantillas.vuelo_cancelado(pasajero.nombre, vuelo, datos.get("es_imputable", False))
        avisos.append(Aviso(tramo.id_detalle_reserva, pasajero.correo, "INTERRUPCION",
                            leer_fecha(datos["fecha_evento_utc"]), correo.asunto, correo.texto, correo.html))
    return avisos


def avisos_vuelo_retrasado(db: Session, datos: dict) -> list[Aviso]:
    vuelo = describir_vuelo(db, datos["id_vuelo"])
    if vuelo is None:
        return []
    avisos = []
    for tramo, pasajero in pasajeros_del_vuelo(db, datos["id_vuelo"]):
        correo = plantillas.vuelo_retrasado(
            pasajero.nombre, vuelo, datos["minutos_retraso"], datos.get("es_imputable", False)
        )
        avisos.append(Aviso(tramo.id_detalle_reserva, pasajero.correo, "INTERRUPCION",
                            leer_fecha(datos["fecha_evento_utc"]), correo.asunto, correo.texto, correo.html))
    return avisos


def avisos_conexion_en_riesgo(db: Session, datos: dict) -> list[Aviso]:
    evaluacion = db.query(EvaluacionConexion).filter_by(id_evaluacion=datos["id_evaluacion"]).first()
    if evaluacion is None:
        return []
    conexion = db.query(ConexionItinerario).filter_by(id_conexion=evaluacion.id_conexion).first()
    if conexion is None:
        return []
    llegada = pasajero_del_tramo(db, conexion.id_detalle_reserva_llegada)
    salida = pasajero_del_tramo(db, conexion.id_detalle_reserva_salida)
    regla = db.query(TiempoMinimoConexion).filter_by(id_regla_conexion=conexion.id_regla_conexion).first()
    if llegada is None or salida is None or regla is None:
        return []
    aeropuerto = db.query(Aeropuerto).filter_by(id_aeropuerto=regla.id_aeropuerto).first()

    tramo_llegada, pasajero = llegada
    tramo_salida, _ = salida
    vuelo_llegada = describir_vuelo(db, tramo_llegada.id_vuelo)
    # Cuánto llega tarde el vuelo: llegada estimada (de la evaluación) menos la llegada programada.
    minutos_retraso = int((en_utc(evaluacion.llegada_estimada_utc) - vuelo_llegada.llegada).total_seconds() // 60)
    correo = plantillas.conexion_en_riesgo(
        pasajero.nombre,
        vuelo_llegada,
        describir_vuelo(db, tramo_salida.id_vuelo),
        aeropuerto.codigo_iata,
        evaluacion.minutos_disponibles,
        evaluacion.minutos_requeridos,
        perdida=evaluacion.estado == "PERDIDA",
        minutos_retraso=max(0, minutos_retraso),
    )
    return [Aviso(tramo_llegada.id_detalle_reserva, pasajero.correo, "CONEXION_RIESGO",
                  evaluacion.fecha_evaluacion_utc, correo.asunto, correo.texto, correo.html,
                  id_evaluacion_conexion=evaluacion.id_evaluacion)]


def avisos_itinerario_cambiado(db: Session, datos: dict) -> list[Aviso]:
    reubicacion = db.query(Reubicacion).filter_by(id_reubicacion=datos["id_reubicacion"]).first()
    if reubicacion is None or reubicacion.id_vuelo_propuesto is None:
        return []
    encontrado = pasajero_del_tramo(db, reubicacion.id_detalle_reserva)
    if encontrado is None:
        return []

    tramo, pasajero = encontrado
    correo = plantillas.itinerario_cambiado(
        pasajero.nombre,
        describir_vuelo(db, tramo.id_vuelo),
        describir_vuelo(db, reubicacion.id_vuelo_propuesto),
        reubicacion.id_reubicacion,
    )
    return [Aviso(tramo.id_detalle_reserva, pasajero.correo, "REUBICACION",
                  reubicacion.fecha_oferta_utc, correo.asunto, correo.texto, correo.html)]


# ── 2. Registrar en la tabla notificacion y enviar ────────────────────────


def registrar_y_enviar(db: Session, enviador, aviso: Aviso) -> str:
    """Devuelve 'enviados', 'omitidos' o 'fallidos'.

    Si RabbitMQ entrega el mismo mensaje dos veces, la segunda vez encontramos la notificación
    ya ENVIADA y no mandamos otro correo. Si antes FALLÓ, se intenta de nuevo.
    """
    notificacion = (
        db.query(Notificacion)
        .filter_by(id_detalle_reserva=aviso.id_detalle_reserva, tipo=aviso.tipo, fecha_programada_utc=aviso.fecha_evento)
        .first()
    )
    if notificacion is not None and notificacion.estado_envio == "ENVIADA":
        return "omitidos"

    if notificacion is None:
        notificacion = Notificacion(
            id_detalle_reserva=aviso.id_detalle_reserva,
            id_evaluacion_conexion=aviso.id_evaluacion_conexion,
            tipo=aviso.tipo,
            canal="EMAIL",
            estado_envio="PENDIENTE",
            fecha_programada_utc=aviso.fecha_evento,
        )
        db.add(notificacion)
        db.commit()  # queda registrada aunque el envío falle

    destinatario, cuerpo, html = elegir_destinatario(aviso)
    if not destinatario:
        print(f"[Worker Notificaciones] ⚠️ El tramo {aviso.id_detalle_reserva} no tiene correo.", flush=True)
        notificacion.estado_envio = "FALLIDA"
        db.commit()
        return "fallidos"

    try:
        enviador.enviar(destinatario, aviso.asunto, cuerpo, html)
        notificacion.estado_envio = "ENVIADA"
        notificacion.fecha_envio_utc = datetime.now(timezone.utc)
        resultado = "enviados"
    except (smtplib.SMTPException, OSError) as e:
        print(f"[Worker Notificaciones] ❌ No se pudo enviar a {destinatario}: {e}", flush=True)
        notificacion.estado_envio = "FALLIDA"
        resultado = "fallidos"
    db.commit()
    return resultado


def elegir_destinatario(aviso: Aviso) -> tuple[str | None, str, str]:
    """Devuelve (destinatario, texto, html).

    Modo pruebas: si EMAIL_DESTINO_PRUEBAS tiene un correo, TODOS los correos van ahí, con un aviso
    de para quién eran. Así no se envían correos reales a las direcciones inventadas del seed.
    """
    destino_pruebas = os.getenv("EMAIL_DESTINO_PRUEBAS", "").strip()
    if not destino_pruebas:
        return aviso.correo, aviso.cuerpo, aviso.html.replace(plantillas.MARCA_MODO_PRUEBAS, "")

    para_quien = aviso.correo or "(sin correo)"
    cuerpo = f"[MODO PRUEBAS] Este correo era para: {para_quien}\n\n{aviso.cuerpo}"
    banner = (
        '<div style="margin:0 0 20px;padding:12px 16px;border-radius:8px;background:#fef9c3;'
        'border:1px solid #facc15;font-size:13px;color:#713f12;">'
        f"<strong>MODO PRUEBAS</strong> · Este correo era para: {escape(para_quien)}</div>"
    )
    return destino_pruebas, cuerpo, aviso.html.replace(plantillas.MARCA_MODO_PRUEBAS, banner)


# ── 3. Todo junto ─────────────────────────────────────────────────────────


def procesar_mensaje(db: Session, routing_key: str, datos: dict, enviador) -> dict:
    resumen = {"enviados": 0, "omitidos": 0, "fallidos": 0}
    for aviso in armar_avisos(db, routing_key, datos):
        resultado = registrar_y_enviar(db, enviador, aviso)
        resumen[resultado] += 1
    return resumen
