import json
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from shared.models.estado_vuelo import EstadoVuelo
from shared.models.evento_operacional import EventoOperacional
from shared.models.vuelo import Vuelo
from shared.models.incidencia_vuelo import IncidenciaVuelo
from shared.models.auditoria_causa import AuditoriaCausa
from shared.notificaciones import CONEXION_EN_RIESGO, ITINERARIO_CAMBIADO, VUELO_CANCELADO, VUELO_RETRASADO
from worker_rds.business_rules import evaluar_auditoria_climatica, resolver_causa
from worker_rds.handlers.pasajeros_afectados import en_utc, evaluar_conexiones, ofrecer_reubicaciones

# OUT/OFF/ON/IN = eventos OOOI. CANCEL = el vuelo se canceló.
CODIGOS_VALIDOS = {"OUT", "OFF", "ON", "IN", "CANCEL"}

# Código del estado "cancelado" en la tabla estado_vuelo (debe coincidir con el seed).
CODIGO_ESTADO_CANCELADO = os.getenv("CODIGO_ESTADO_CANCELADO", "CANCELADO")

# A partir de cuántos minutos de retraso se avisa al pasajero por correo.
UMBRAL_RETRASO_NOTIFICACION_MIN = int(os.getenv("UMBRAL_RETRASO_NOTIFICACION_MIN", "120"))


def procesar_evento_oooi(body: bytes | str | dict, db: Session, publicar=None) -> str:
    """
    Procesa un evento OOOI (OUT, OFF, ON, IN) o una cancelación (CANCEL) originado por el simulador.

    publicar: función opcional publicar(routing_key, datos) para enviar notificaciones a RabbitMQ.
    Las notificaciones se publican DESPUÉS del commit, para no avisar de algo que no quedó guardado.

    Retorna:
      - 'ok': procesado y persistido correctamente.
      - 'duplicado': ya existía en la base de datos (RN-09 idempotencia).
      - 'invalido': estructura malformada o código de evento no reconocido.
    """
    if isinstance(body, (bytes, str)):
        data = json.loads(body)
    else:
        data = body

    # ── 1. Validación estructural básica ──────────────────────────────
    id_externo = data.get("id_externo_evento")
    codigo_evento = data.get("codigo_evento")
    id_vuelo = data.get("id_vuelo")

    if not id_externo or not codigo_evento or codigo_evento not in CODIGOS_VALIDOS or not id_vuelo:
        return "invalido"

    # ── 2. Idempotencia (RN-09) ───────────────────────────────────────
    # Un evento repetido se descarta aquí, así que tampoco se vuelve a notificar.
    existente = (
        db.query(EventoOperacional)
        .filter_by(id_externo_evento=str(id_externo))
        .first()
    )
    if existente:
        return "duplicado"

    # ── 3. Detección de caos y validación de calidad (HU-05) ──────────
    fecha_raw = data.get("fecha_hora_evento_utc")
    try:
        fecha_evento = datetime.fromisoformat(str(fecha_raw))
        if fecha_evento.tzinfo is None:
            fecha_evento = fecha_evento.replace(tzinfo=timezone.utc)
    except Exception:
        return "invalido"

    codigo_causa = data.get("codigo_causa_original")
    id_causa, es_imputable, causa_valida = resolver_causa(codigo_causa, db=db)

    # Evaluación de estado de validación (restricción BD: PENDIENTE, VALIDO, RECHAZADO)
    if fecha_evento.year < 2020:
        estado_validacion = "RECHAZADO"
        detalle_validacion = f"Año anómalo detectado: {fecha_evento.year} (Paradoja de tiempo)"
    elif codigo_causa and not causa_valida:
        estado_validacion = "RECHAZADO"
        detalle_validacion = f"Causa no reconocida en catálogo: {codigo_causa}"
    else:
        estado_validacion = "VALIDO"
        detalle_validacion = None

    ahora_utc = datetime.now(timezone.utc)

    estado_cancelado = None
    if codigo_evento == "CANCEL":
        estado_cancelado = db.query(EstadoVuelo).filter_by(codigo=CODIGO_ESTADO_CANCELADO).first()
        if estado_cancelado is None:
            print(f"[Worker RDS] ⚠️ No existe el estado '{CODIGO_ESTADO_CANCELADO}' en estado_vuelo.", flush=True)

    # ── 4. Insertar en evento_operacional ─────────────────────────────
    nuevo_evento = EventoOperacional(
        id_vuelo=int(id_vuelo),
        id_estado_vuelo=estado_cancelado.id_estado_vuelo if estado_cancelado else 1,  # 1 = Programado / En Progreso
        fecha_hora_evento_utc=fecha_evento,
        fecha_hora_recepcion_utc=ahora_utc,
        codigo_evento=codigo_evento,
        codigo_causa_original=codigo_causa,
        id_externo_evento=str(id_externo),
        estado_validacion=estado_validacion,
        detalle_validacion=detalle_validacion,
        fecha_procesamiento_utc=ahora_utc,
    )
    db.add(nuevo_evento)
    db.flush()  # Para obtener el id_evento si se requiere FK

    # Notificaciones a publicar cuando el commit termine: lista de (routing_key, datos).
    notificaciones = []

    # ── 5. Actualizar tiempos reales en vuelo e incidencia ─────────────
    if estado_validacion == "VALIDO":
        vuelo = db.query(Vuelo).filter_by(id_vuelo=int(id_vuelo)).first()
        if vuelo and codigo_evento == "CANCEL":
            notificaciones = procesar_cancelacion(
                db, vuelo, nuevo_evento, id_causa, es_imputable, estado_cancelado, fecha_evento, ahora_utc
            )
        elif vuelo:
            campo_map = {
                "OUT": "salida_real_puerta_utc",
                "OFF": "despegue_real_utc",
                "ON":  "aterrizaje_real_utc",
                "IN":  "llegada_real_puerta_utc",
            }
            campo_a_actualizar = campo_map.get(codigo_evento)
            if campo_a_actualizar:
                setattr(vuelo, campo_a_actualizar, fecha_evento)

            if codigo_evento == "OUT":
                minutos_retraso = 0
                if vuelo.salida_programada_utc:
                    prog = en_utc(vuelo.salida_programada_utc)
                    minutos_retraso = max(0, int((fecha_evento - prog).total_seconds() / 60))

                # Si tiene retraso con causa, registrar incidencia
                if minutos_retraso > 0 and id_causa:
                    requiere_auditoria, obs_origen, obs_destino = evaluar_auditoria_climatica(
                        db, vuelo.id_ruta, fecha_evento, codigo_causa
                    )
                    incidencia = IncidenciaVuelo(
                        id_vuelo=vuelo.id_vuelo,
                        id_evento_origen=nuevo_evento.id_evento,
                        id_causa=id_causa,
                        tipo="RETRASO",
                        minutos_retraso=minutos_retraso,
                        es_causa_principal=True,
                        requiere_auditoria=requiere_auditoria,
                        estado_revision="PENDIENTE",
                        fecha_clasificacion_utc=ahora_utc,
                    )
                    db.add(incidencia)
                    if requiere_auditoria:
                        db.flush()
                        _registrar_auditoria_climatica(
                            db, incidencia, obs_origen, obs_destino, ahora_utc
                        )

                if minutos_retraso > 0:
                    notificaciones = procesar_retraso(
                        db, vuelo, minutos_retraso, codigo_causa, es_imputable, fecha_evento, ahora_utc
                    )

    db.commit()

    # ── 6. Avisar a los pasajeros (solo cuando todo quedó guardado) ────
    if publicar is not None:
        for routing_key, datos in notificaciones:
            try:
                publicar(routing_key, datos)
            except Exception as e:
                # El evento ya está guardado: no lo devolvemos a la cola por un fallo al notificar.
                print(f"[Worker RDS] ⚠️ No se pudo publicar la notificación {routing_key}: {e}", flush=True)

    return "ok"


def procesar_cancelacion(db, vuelo, evento, id_causa, es_imputable, estado_cancelado, fecha_evento, ahora_utc):
    """Marca el vuelo como cancelado, registra la incidencia y ofrece reubicaciones. Devuelve las notificaciones."""
    if estado_cancelado is not None:
        vuelo.id_estado_vuelo_actual = estado_cancelado.id_estado_vuelo

    notificaciones = [
        (VUELO_CANCELADO, {
            "id_vuelo": vuelo.id_vuelo,
            "fecha_evento_utc": fecha_evento.isoformat(),
            "codigo_causa": evento.codigo_causa_original,
            "es_imputable": es_imputable,
        })
    ]

    # La incidencia (y por tanto la reubicación) necesita una causa válida.
    if id_causa:
        requiere_auditoria, obs_origen, obs_destino = evaluar_auditoria_climatica(
            db, vuelo.id_ruta, fecha_evento, evento.codigo_causa_original
        )
        incidencia = IncidenciaVuelo(
            id_vuelo=vuelo.id_vuelo,
            id_evento_origen=evento.id_evento,
            id_causa=id_causa,
            tipo="CANCELACION",
            minutos_retraso=None,
            es_causa_principal=True,
            requiere_auditoria=requiere_auditoria,
            estado_revision="PENDIENTE",
            fecha_clasificacion_utc=ahora_utc,
        )
        db.add(incidencia)
        db.flush()

        if requiere_auditoria:
            _registrar_auditoria_climatica(db, incidencia, obs_origen, obs_destino, ahora_utc)

        id_estado_cancelado = estado_cancelado.id_estado_vuelo if estado_cancelado else None
        for reubicacion in ofrecer_reubicaciones(db, vuelo, incidencia, id_estado_cancelado, ahora_utc):
            if reubicacion.estado == "OFRECIDA":
                notificaciones.append((ITINERARIO_CAMBIADO, {"id_reubicacion": reubicacion.id_reubicacion}))

    return notificaciones


def _registrar_auditoria_climatica(db, incidencia, obs_origen, obs_destino, ahora_utc):
    """RN-04: deja evidencia de la revisión climática de una causa técnica."""
    db.add(
        AuditoriaCausa(
            id_incidencia=incidencia.id_incidencia,
            id_observacion_clima_origen=obs_origen,
            id_observacion_clima_destino=obs_destino,
            motivo=(
                "Causa técnica con condición climática adversa (viento > 50 km/h o "
                "visibilidad < 1 km) en origen o destino dentro de una hora del evento."
            ),
            estado="PENDIENTE",
            fecha_creacion_utc=ahora_utc,
        )
    )


def procesar_retraso(db, vuelo, minutos_retraso, codigo_causa, es_imputable, fecha_evento, ahora_utc):
    """Evalúa las conexiones afectadas por el retraso (RN-07). Devuelve las notificaciones."""
    notificaciones = []

    if minutos_retraso >= UMBRAL_RETRASO_NOTIFICACION_MIN:
        notificaciones.append((VUELO_RETRASADO, {
            "id_vuelo": vuelo.id_vuelo,
            "fecha_evento_utc": fecha_evento.isoformat(),
            "minutos_retraso": minutos_retraso,
            "codigo_causa": codigo_causa,
            "es_imputable": es_imputable,
        }))

    for evaluacion in evaluar_conexiones(db, vuelo, minutos_retraso, ahora_utc):
        notificaciones.append((CONEXION_EN_RIESGO, {"id_evaluacion": evaluacion.id_evaluacion}))

    return notificaciones
