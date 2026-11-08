"""Consultas de solo lectura para la API de pasajeros (RF-06 / RNF-04).

Diseño de rendimiento (RNF-04, p95 <= 300 ms):
- El grafo pasajero -> reserva_pasajero -> itinerario -> detalle_reserva -> vuelo
  se carga con `selectinload` encadenado y `joinedload` en las ramas de cardinalidad 1
  (vuelo, ruta, aeropuertos, estado, vuelo propuesto).
- Las tablas que viven en el registro ORM de `app.models` (reserva, compensacion, pago,
  notificacion) se traen con una consulta `IN (...)` por tabla, nunca dentro de un bucle.
- Resultado: el número de sentencias SQL es constante (no crece con la cantidad de
  tramos del pasajero), que es exactamente lo que elimina el N+1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.compensacion import Compensacion
from app.models.pago import Pago
from app.models.reserva import Reserva
from shared.models.conexion_itinerario import ConexionItinerario
from shared.models.detalle_reserva import DetalleReserva
from shared.models.evaluacion_conexion import EvaluacionConexion
from shared.models.itinerario import Itinerario
from shared.models.notificacion import Notificacion
from shared.models.pasajero import Pasajero
from shared.models.reserva_pasajero import ReservaPasajero
from shared.models.reubicacion import Reubicacion
from shared.models.ruta import Ruta
from shared.models.vuelo import Vuelo

# RN-01: un vuelo es puntual si el retraso de llegada es menor o igual a 15 minutos.
UMBRAL_OTP_MINUTOS = 15


# ── Utilidades ────────────────────────────────────────────────────────────


def a_utc(fecha: datetime | None) -> datetime | None:
    """Normaliza a UTC una fecha que puede venir sin zona horaria."""
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha


def minutos_de_retraso(real: datetime | None, programada: datetime | None) -> int | None:
    """Diferencia en minutos (real - programada). `None` si el evento aún no ocurrió."""
    real_utc, prog_utc = a_utc(real), a_utc(programada)
    if real_utc is None or prog_utc is None:
        return None
    return int((real_utc - prog_utc).total_seconds() // 60)


# ── Carga del grafo completo (una sola pasada) ────────────────────────────


def _opciones_grafo():
    """Opciones de eager loading para el grafo del pasajero."""
    return (
        selectinload(Pasajero.reservas)
        .selectinload(ReservaPasajero.itinerarios)
        .selectinload(Itinerario.tramos)
        .options(
            joinedload(DetalleReserva.vuelo)
            .joinedload(Vuelo.ruta)
            .joinedload(Ruta.aeropuerto_origen),
            joinedload(DetalleReserva.vuelo)
            .joinedload(Vuelo.ruta)
            .joinedload(Ruta.aeropuerto_destino),
            joinedload(DetalleReserva.vuelo).joinedload(Vuelo.estado_actual),
            selectinload(DetalleReserva.conexiones_salida)
            .selectinload(ConexionItinerario.evaluaciones),
            selectinload(DetalleReserva.reubicaciones)
            .joinedload(Reubicacion.vuelo_propuesto)
            .joinedload(Vuelo.ruta)
            .joinedload(Ruta.aeropuerto_origen),
            selectinload(DetalleReserva.reubicaciones)
            .joinedload(Reubicacion.vuelo_propuesto)
            .joinedload(Vuelo.ruta)
            .joinedload(Ruta.aeropuerto_destino),
            # El estado del vuelo propuesto también se pinta en la respuesta: se carga
            # aquí para que `_reubicacion_resumen` no dispare una consulta por propuesta.
            selectinload(DetalleReserva.reubicaciones)
            .joinedload(Reubicacion.vuelo_propuesto)
            .joinedload(Vuelo.estado_actual),
        )
    )


def get_pasajero_con_grafo(db: Session, id_pasajero: int) -> Pasajero | None:
    """Pasajero con reservas, itinerarios, tramos, vuelos, conexiones y reubicaciones cargados."""
    return db.execute(
        select(Pasajero).where(Pasajero.id_pasajero == id_pasajero).options(_opciones_grafo())
    ).scalar_one_or_none()


def get_pasajero(db: Session, id_pasajero: int) -> Pasajero | None:
    """Perfil básico, sin cargar el grafo."""
    return db.get(Pasajero, id_pasajero)


def get_reserva_por_codigo(db: Session, codigo_reserva: str) -> Reserva | None:
    """Reserva por su código único."""
    return db.execute(
        select(Reserva).where(Reserva.codigo_reserva == codigo_reserva.strip().upper())
    ).scalar_one_or_none()


def pasajero_tiene_reserva(db: Session, id_reserva: int, id_pasajero: int) -> bool:
    """RN-11: una reserva puede tener varios pasajeros; cualquiera de ellos puede consultarla."""
    return (
        db.execute(
            select(ReservaPasajero.id_reserva_pasajero).where(
                ReservaPasajero.id_reserva == id_reserva,
                ReservaPasajero.id_pasajero == id_pasajero,
            )
        ).first()
        is not None
    )


def get_reservas_por_ids(db: Session, ids_reserva: list[int]) -> dict[int, Reserva]:
    """Reservas del registro `app.models`, indexadas por id (una sola consulta)."""
    if not ids_reserva:
        return {}
    filas = db.execute(select(Reserva).where(Reserva.id_reserva.in_(ids_reserva))).scalars().all()
    return {r.id_reserva: r for r in filas}


# ── Detalles de tripulación de datos ──────────────────────────────────────


def get_compensaciones_por_detalles(
    db: Session, ids_detalle_reserva: list[int]
) -> dict[int, Compensacion]:
    """Compensaciones indexadas por `id_detalle_reserva` (RN-09: máximo una por segmento)."""
    if not ids_detalle_reserva:
        return {}
    filas = (
        db.execute(select(Compensacion).where(Compensacion.id_detalle_reserva.in_(ids_detalle_reserva)))
        .scalars()
        .all()
    )
    return {c.id_detalle_reserva: c for c in filas}


def get_pagos_por_compensaciones(
    db: Session, ids_compensacion: list[int]
) -> dict[int, Pago]:
    """Pagos indexados por `id_compensacion` (una sola consulta)."""
    if not ids_compensacion:
        return {}
    filas = (
        db.execute(select(Pago).where(Pago.id_compensacion.in_(ids_compensacion))).scalars().all()
    )
    return {p.id_compensacion: p for p in filas}


def get_notificaciones_por_detalles(
    db: Session, ids_detalle_reserva: list[int]
) -> dict[int, list[Notificacion]]:
    """Notificaciones agrupadas por `id_detalle_reserva` (una sola consulta)."""
    if not ids_detalle_reserva:
        return {}
    filas = (
        db.execute(
            select(Notificacion)
            .where(Notificacion.id_detalle_reserva.in_(ids_detalle_reserva))
            .order_by(Notificacion.fecha_programada_utc.desc())
        )
        .scalars()
        .all()
    )
    agrupadas: dict[int, list[Notificacion]] = {}
    for n in filas:
        agrupadas.setdefault(n.id_detalle_reserva, []).append(n)
    return agrupadas


# ── Armado de respuestas ──────────────────────────────────────────────────


def _aeropuerto(aeropuerto) -> dict | None:
    if aeropuerto is None:
        return None
    return {"codigo_iata": aeropuerto.codigo_iata, "nombre": aeropuerto.nombre}


def _tramo_resumen(detalle: DetalleReserva) -> dict:
    """Tramo con vuelo, ruta, retrasos y OTP (RN-01)."""
    vuelo: Vuelo | None = detalle.vuelo
    ruta: Ruta | None = vuelo.ruta if vuelo else None
    retraso_salida = minutos_de_retraso(
        vuelo.salida_real_puerta_utc if vuelo else None,
        vuelo.salida_programada_utc if vuelo else None,
    )
    retraso_llegada = minutos_de_retraso(
        vuelo.llegada_real_puerta_utc if vuelo else None,
        vuelo.llegada_programada_utc if vuelo else None,
    )
    return {
        "id_detalle_reserva": detalle.id_detalle_reserva,
        "numero_secuencia": detalle.numero_secuencia,
        "numero_vuelo": vuelo.numero_vuelo if vuelo else "",
        "origen": _aeropuerto(ruta.aeropuerto_origen if ruta else None),
        "destino": _aeropuerto(ruta.aeropuerto_destino if ruta else None),
        "salida_programada_utc": a_utc(vuelo.salida_programada_utc) if vuelo else None,
        "llegada_programada_utc": a_utc(vuelo.llegada_programada_utc) if vuelo else None,
        "salida_real_utc": a_utc(vuelo.salida_real_puerta_utc) if vuelo else None,
        "llegada_real_utc": a_utc(vuelo.llegada_real_puerta_utc) if vuelo else None,
        "estado_vuelo": vuelo.estado_actual.nombre if vuelo and vuelo.estado_actual else None,
        "estado_segmento": detalle.estado_segmento,
        "clase_servicio": detalle.clase_servicio,
        "clase_tarifaria": detalle.clase_tarifaria,
        "numero_asiento": detalle.numero_asiento,
        "monto_tarifa_pagada": detalle.monto_tarifa_pagada,
        "moneda": detalle.moneda,
        "retraso_salida_min": retraso_salida,
        "retraso_llegada_min": retraso_llegada,
        "es_otp": None if retraso_llegada is None else retraso_llegada <= UMBRAL_OTP_MINUTOS,
    }


def _evaluacion_resumen(evaluacion: EvaluacionConexion) -> dict:
    return {
        "id_evaluacion": evaluacion.id_evaluacion,
        "fecha_evaluacion_utc": a_utc(evaluacion.fecha_evaluacion_utc),
        "llegada_estimada_utc": a_utc(evaluacion.llegada_estimada_utc),
        "salida_estimada_utc": a_utc(evaluacion.salida_estimada_utc),
        "minutos_disponibles": evaluacion.minutos_disponibles,
        "minutos_requeridos": evaluacion.minutos_requeridos,
        "estado": evaluacion.estado,
    }


def _reubicacion_resumen(reubicacion: Reubicacion) -> dict:
    propuesto = reubicacion.vuelo_propuesto
    return {
        "id_reubicacion": reubicacion.id_reubicacion,
        "id_incidencia": reubicacion.id_incidencia,
        "estado": reubicacion.estado,
        "fecha_oferta_utc": a_utc(reubicacion.fecha_oferta_utc),
        "fecha_respuesta_utc": a_utc(reubicacion.fecha_respuesta_utc),
        "vuelo_propuesto": (
            {
                "id_detalle_reserva": reubicacion.id_detalle_reserva,
                "numero_secuencia": 0,
                "numero_vuelo": propuesto.numero_vuelo,
                "origen": _aeropuerto(propuesto.ruta.aeropuerto_origen if propuesto.ruta else None),
                "destino": _aeropuerto(propuesto.ruta.aeropuerto_destino if propuesto.ruta else None),
                "salida_programada_utc": a_utc(propuesto.salida_programada_utc),
                "llegada_programada_utc": a_utc(propuesto.llegada_programada_utc),
                "salida_real_utc": a_utc(propuesto.salida_real_puerta_utc),
                "llegada_real_utc": a_utc(propuesto.llegada_real_puerta_utc),
                "estado_vuelo": propuesto.estado_actual.nombre if propuesto.estado_actual else None,
                "estado_segmento": "PROPUESTO",
                "clase_servicio": "",
                "clase_tarifaria": None,
                "numero_asiento": None,
                "monto_tarifa_pagada": Decimal("0.00"),
                "moneda": "USD",
                "retraso_salida_min": None,
                "retraso_llegada_min": None,
                "es_otp": None,
            }
            if propuesto is not None
            else None
        ),
    }


def _armar_itinerarios(itinerarios_orm: list[Itinerario]) -> list[dict]:
    """Convierte itinerarios ORM (ya cargados) a su representación de respuesta."""
    itinerarios = []
    for itinerario in itinerarios_orm:
        tramos = []
        conexiones = []
        for detalle in itinerario.tramos:
            resumen = _tramo_resumen(detalle)
            resumen["reubicaciones"] = [_reubicacion_resumen(r) for r in detalle.reubicaciones]
            tramos.append(resumen)

            for conexion in detalle.conexiones_salida:
                evaluaciones = list(conexion.evaluaciones)
                conexiones.append(
                    {
                        "id_conexion": conexion.id_conexion,
                        "id_detalle_reserva_llegada": conexion.id_detalle_reserva_llegada,
                        "id_detalle_reserva_salida": conexion.id_detalle_reserva_salida,
                        "estado": evaluaciones[0].estado if evaluaciones else None,
                        "ultima_evaluacion": _evaluacion_resumen(evaluaciones[0]) if evaluaciones else None,
                        "evaluaciones": [_evaluacion_resumen(e) for e in evaluaciones],
                    }
                )

        itinerarios.append(
            {
                "id_itinerario": itinerario.id_itinerario,
                "estado": itinerario.estado,
                "fecha_salida_utc": a_utc(itinerario.fecha_salida_utc),
                "fecha_creacion_utc": a_utc(itinerario.fecha_creacion_utc),
                "fecha_actualizacion_utc": a_utc(itinerario.fecha_actualizacion_utc),
                "tramos": tramos,
                "conexiones": conexiones,
            }
        )
    return itinerarios


def _compensaciones_de_itinerarios(
    db: Session, itinerarios_orm: list[Itinerario]
) -> tuple[list[dict], dict]:
    """Compensaciones de los tramos indicados, con pago y notificaciones.

    Recibe los itinerarios ya cargados (no vuelve a consultar el grafo del pasajero),
    de modo que el endpoint de una reserva concreta nunca mezcla datos de otras reservas.
    """
    detalles = [detalle for itinerario in itinerarios_orm for detalle in itinerario.tramos]
    ids_detalle = [detalle.id_detalle_reserva for detalle in detalles]
    compensaciones = get_compensaciones_por_detalles(db, ids_detalle)
    if not compensaciones:
        return [], {
            "total_compensaciones": 0,
            "monto_total": Decimal("0.00"),
            "moneda": None,
            "por_estado": {},
        }

    pagos = get_pagos_por_compensaciones(db, [c.id_compensacion for c in compensaciones.values()])
    notificaciones = get_notificaciones_por_detalles(db, ids_detalle)

    # Número de vuelo por tramo para dar contexto en la respuesta.
    numero_vuelo_por_detalle = {
        detalle.id_detalle_reserva: (detalle.vuelo.numero_vuelo if detalle.vuelo else None)
        for detalle in detalles
    }

    salida = []
    total = Decimal("0.00")
    moneda: str | None = None
    por_estado: dict[str, int] = {}
    for id_detalle, comp in sorted(compensaciones.items()):
        pago = pagos.get(comp.id_compensacion)
        salida.append(
            {
                "id_compensacion": comp.id_compensacion,
                "id_detalle_reserva": comp.id_detalle_reserva,
                "id_incidencia": comp.id_incidencia,
                "id_regla_compensacion": comp.id_regla_compensacion,
                "minutos_imputables": comp.minutos_imputables,
                "monto": comp.monto,
                "moneda": comp.moneda,
                "fecha_calculo_utc": a_utc(comp.fecha_calculo_utc),
                "estado": comp.estado,
                "numero_vuelo": numero_vuelo_por_detalle.get(id_detalle),
                "pago": (
                    {
                        "id_pago": pago.id_pago,
                        "clave_idempotencia": pago.clave_idempotencia,
                        "id_transaccion_externa": pago.id_transaccion_externa,
                        "estado": pago.estado,
                        "fecha_solicitud_utc": a_utc(pago.fecha_solicitud_utc),
                        "fecha_actualizacion_utc": a_utc(pago.fecha_actualizacion_utc),
                    }
                    if pago is not None
                    else None
                ),
                "notificaciones": [
                    {
                        "id_notificacion": n.id_notificacion,
                        "id_detalle_reserva": n.id_detalle_reserva,
                        "id_evaluacion_conexion": n.id_evaluacion_conexion,
                        "id_compensacion": n.id_compensacion,
                        "tipo": n.tipo,
                        "canal": n.canal,
                        "estado_envio": n.estado_envio,
                        "fecha_programada_utc": a_utc(n.fecha_programada_utc),
                        "fecha_envio_utc": a_utc(n.fecha_envio_utc),
                    }
                    for n in notificaciones.get(id_detalle, [])
                    if n.id_compensacion in (None, comp.id_compensacion)
                ],
            }
        )
        total += comp.monto
        moneda = moneda or comp.moneda
        por_estado[comp.estado] = por_estado.get(comp.estado, 0) + 1

    return salida, {
        "total_compensaciones": len(salida),
        "monto_total": total,
        "moneda": moneda,
        "por_estado": por_estado,
    }


# ── Vistas de alto nivel que consume el router ────────────────────────────


def perfil_pasajero(db: Session, id_pasajero: int) -> dict | None:
    pasajero = get_pasajero_con_grafo(db, id_pasajero)
    if pasajero is None:
        return None
    return {"pasajero": pasajero}


def itinerarios_pasajero(db: Session, id_pasajero: int) -> dict | None:
    """Reservas del pasajero, cada una con sus itinerarios, tramos y conexiones."""
    pasajero = get_pasajero_con_grafo(db, id_pasajero)
    if pasajero is None:
        return None

    reservas_info = get_reservas_por_ids(db, [r.id_reserva for r in pasajero.reservas])

    reservas = []
    for rp in pasajero.reservas:
        reserva = reservas_info.get(rp.id_reserva)

        # Se arma por reserva (no en bloque) para poder anidar cada itinerario
        # bajo el id_reserva_pasajero al que pertenece.
        itinerarios = []
        for itinerario in rp.itinerarios:
            armados = _armar_itinerarios([itinerario])
            itinerarios.extend(armados)

        reservas.append(
            {
                "id_reserva": rp.id_reserva,
                "codigo_reserva": reserva.codigo_reserva if reserva else None,
                "estado_reserva": reserva.estado_reserva if reserva else None,
                "fecha_reserva_utc": a_utc(reserva.fecha_reserva_utc) if reserva else None,
                "itinerarios": itinerarios,
            }
        )
    return {"pasajero": pasajero, "reservas": reservas}


def _itinerarios_crudos(pasajero: Pasajero) -> list[Itinerario]:
    return [i for reserva in pasajero.reservas for i in reserva.itinerarios]


def compensaciones_pasajero(db: Session, id_pasajero: int) -> dict | None:
    pasajero = get_pasajero_con_grafo(db, id_pasajero)
    if pasajero is None:
        return None
    compensaciones, resumen = _compensaciones_de_itinerarios(db, _itinerarios_crudos(pasajero))
    return {"pasajero": pasajero, "compensaciones": compensaciones, "resumen": resumen}


def estado_reserva(db: Session, id_reserva: int, id_pasajero: int) -> dict | None:
    """Estado consolidado de una reserva del pasajero (RN-11 ya validado por el router)."""
    pasajero = get_pasajero_con_grafo(db, id_pasajero)
    if pasajero is None:
        return None

    reservas_propias = [rp for rp in pasajero.reservas if rp.id_reserva == id_reserva]
    if not reservas_propias:
        return None

    info = get_reservas_por_ids(db, [id_reserva]).get(id_reserva)
    if info is None:
        return None

    # RN-11: solo se arman los itinerarios y compensaciones de la reserva solicitada,
    # aunque el pasajero tenga otras reservas cargadas en el mismo grafo.
    itinerarios_orm = [i for rp in reservas_propias for i in rp.itinerarios]
    itinerarios = _armar_itinerarios(itinerarios_orm)
    compensaciones, resumen_comp = _compensaciones_de_itinerarios(db, itinerarios_orm)

    total_vuelos = sum(len(i["tramos"]) for i in itinerarios)
    vuelos_afectados = sum(
        1
        for i in itinerarios
        for t in i["tramos"]
        if (t["retraso_llegada_min"] or 0) > UMBRAL_OTP_MINUTOS
        or (t["estado_vuelo"] or "").upper() in ("CANCELADO", "DESVIADO")
    )
    conexiones_en_riesgo = sum(
        1 for i in itinerarios for c in i["conexiones"] if c["estado"] in ("EN_RIESGO", "PERDIDA")
    )
    reubicaciones_ofrecidas = sum(
        1 for i in itinerarios for t in i["tramos"] for r in t["reubicaciones"] if r["estado"] == "OFRECIDA"
    )

    return {
        "id_reserva": info.id_reserva,
        "codigo_reserva": info.codigo_reserva,
        "estado_reserva": info.estado_reserva,
        "fecha_reserva_utc": a_utc(info.fecha_reserva_utc),
        "fecha_actualizacion_utc": a_utc(info.fecha_actualizacion_utc),
        "itinerarios": itinerarios,
        "compensaciones": compensaciones,
        "resumen": {
            "total_vuelos": total_vuelos,
            "vuelos_afectados": vuelos_afectados,
            "conexiones_en_riesgo": conexiones_en_riesgo,
            "reubicaciones_ofrecidas": reubicaciones_ofrecidas,
            "total_compensaciones": resumen_comp["total_compensaciones"],
            "monto_compensado": resumen_comp["monto_total"],
            "moneda": resumen_comp["moneda"],
        },
    }
