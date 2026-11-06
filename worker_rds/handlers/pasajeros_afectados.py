"""Qué les pasa a los pasajeros cuando un vuelo se retrasa o se cancela."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from shared.models.conexion_itinerario import ConexionItinerario
from shared.models.detalle_reserva import DetalleReserva
from shared.models.evaluacion_conexion import EvaluacionConexion
from shared.models.incidencia_vuelo import IncidenciaVuelo
from shared.models.reubicacion import Reubicacion
from shared.models.tiempo_minimo_conexion import TiempoMinimoConexion
from shared.models.vuelo import Vuelo


def en_utc(fecha: datetime) -> datetime:
    """Si la fecha viene sin zona horaria, sabemos que está guardada en UTC."""
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha


def tramos_del_vuelo(db: Session, id_vuelo: int) -> list[DetalleReserva]:
    """Todos los tramos (un pasajero en este vuelo = un tramo)."""
    return db.query(DetalleReserva).filter_by(id_vuelo=id_vuelo).all()


def evaluar_conexiones(db: Session, vuelo: Vuelo, minutos_retraso: int, ahora: datetime) -> list[EvaluacionConexion]:
    """RN-07: una conexión está en riesgo si el tiempo entre la llegada proyectada y la salida
    del siguiente tramo es menor que el tiempo mínimo de conexión del aeropuerto.

    Guarda una evaluación por cada conexión de los pasajeros que llegan en este vuelo
    y devuelve solo las que quedaron EN_RIESGO o PERDIDA.
    """
    ids_tramos = [tramo.id_detalle_reserva for tramo in tramos_del_vuelo(db, vuelo.id_vuelo)]
    if not ids_tramos:
        return []

    conexiones = (
        db.query(ConexionItinerario)
        .filter(ConexionItinerario.id_detalle_reserva_llegada.in_(ids_tramos))
        .all()
    )

    llegada_estimada = en_utc(vuelo.llegada_programada_utc) + timedelta(minutes=minutos_retraso)
    en_riesgo = []
    for conexion in conexiones:
        tramo_siguiente = db.query(DetalleReserva).filter_by(id_detalle_reserva=conexion.id_detalle_reserva_salida).first()
        vuelo_siguiente = db.query(Vuelo).filter_by(id_vuelo=tramo_siguiente.id_vuelo).first() if tramo_siguiente else None
        regla = db.query(TiempoMinimoConexion).filter_by(id_regla_conexion=conexion.id_regla_conexion).first()
        if vuelo_siguiente is None or regla is None:
            continue  # datos incompletos: no podemos evaluar esta conexión

        salida_siguiente = en_utc(vuelo_siguiente.salida_programada_utc)
        minutos_disponibles = int((salida_siguiente - llegada_estimada).total_seconds() // 60)

        if minutos_disponibles < 0:
            estado = "PERDIDA"  # llega después de que sale el siguiente vuelo
        elif minutos_disponibles < regla.minutos_minimos:
            estado = "EN_RIESGO"
        else:
            estado = "NORMAL"

        evaluacion = EvaluacionConexion(
            id_conexion=conexion.id_conexion,
            fecha_evaluacion_utc=ahora,
            llegada_estimada_utc=llegada_estimada,
            salida_estimada_utc=salida_siguiente,
            minutos_disponibles=minutos_disponibles,
            minutos_requeridos=regla.minutos_minimos,
            estado=estado,
        )
        db.add(evaluacion)
        if estado != "NORMAL":
            en_riesgo.append(evaluacion)

    db.flush()  # para que cada evaluación tenga su id antes de publicar el mensaje
    return en_riesgo


def ofrecer_reubicaciones(
    db: Session, vuelo: Vuelo, incidencia: IncidenciaVuelo, id_estado_cancelado: int | None, ahora: datetime
) -> list[Reubicacion]:
    """RN-05/RN-06: a cada pasajero de un vuelo cancelado se le ofrece el siguiente vuelo de la misma ruta.

    Si no hay vuelo alternativo, la reubicación queda PENDIENTE (alguien de servicio al cliente la asigna).
    """
    consulta_alternativo = db.query(Vuelo).filter(
        Vuelo.id_ruta == vuelo.id_ruta,
        Vuelo.id_vuelo != vuelo.id_vuelo,
        Vuelo.salida_programada_utc > vuelo.salida_programada_utc,
    )
    if id_estado_cancelado is not None:
        consulta_alternativo = consulta_alternativo.filter(Vuelo.id_estado_vuelo_actual != id_estado_cancelado)
    alternativo = consulta_alternativo.order_by(Vuelo.salida_programada_utc).first()

    reubicaciones = []
    for tramo in tramos_del_vuelo(db, vuelo.id_vuelo):
        reubicacion = Reubicacion(
            id_detalle_reserva=tramo.id_detalle_reserva,
            id_incidencia=incidencia.id_incidencia,
            id_vuelo_propuesto=alternativo.id_vuelo if alternativo else None,
            estado="OFRECIDA" if alternativo else "PENDIENTE",
            fecha_oferta_utc=ahora if alternativo else None,
        )
        db.add(reubicacion)
        reubicaciones.append(reubicacion)

    db.flush()
    return reubicaciones
