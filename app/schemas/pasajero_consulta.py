"""Esquemas de respuesta de la API de consulta para pasajeros (RF-06).

Todos son de solo lectura: representan el grafo
pasajero -> reserva_pasajero -> itinerario -> detalle_reserva -> vuelo
más las conexiones evaluadas, las reubicaciones propuestas y las compensaciones/pagos.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Perfil ────────────────────────────────────────────────────────────────


class PasajeroPerfilResponse(BaseModel):
    """Perfil básico del pasajero (RF-06)."""

    model_config = ConfigDict(from_attributes=True)

    id_pasajero: int
    nombre: str
    apellido: str
    documento: str
    tipo_documento: str
    fecha_nacimiento: date
    correo: str | None = None
    telefono: str | None = None


# ── Tramos y vuelos ───────────────────────────────────────────────────────


class AeropuertoResumen(BaseModel):
    """Aeropuerto en formato compacto para la respuesta."""

    codigo_iata: str
    nombre: str


class EvaluacionConexionResumen(BaseModel):
    """Evaluación RN-07 de una conexión: minutos disponibles vs requeridos."""

    model_config = ConfigDict(from_attributes=True)

    id_evaluacion: int
    fecha_evaluacion_utc: datetime
    llegada_estimada_utc: datetime
    salida_estimada_utc: datetime
    minutos_disponibles: int
    minutos_requeridos: int
    estado: Literal["NORMAL", "EN_RIESGO", "PERDIDA"]


class ConexionResumen(BaseModel):
    """Conexión del itinerario con su última evaluación y su historial."""

    id_conexion: int
    id_detalle_reserva_llegada: int
    id_detalle_reserva_salida: int
    estado: Literal["NORMAL", "EN_RIESGO", "PERDIDA"] | None = None
    ultima_evaluacion: EvaluacionConexionResumen | None = None
    evaluaciones: list[EvaluacionConexionResumen] = Field(default_factory=list)


class ReubicacionResumen(BaseModel):
    """Propuesta de reubicación ofrecida al pasajero (RN-05 / RN-06)."""

    id_reubicacion: int
    id_incidencia: int
    estado: Literal["PENDIENTE", "OFRECIDA", "ACEPTADA", "RECHAZADA", "COMPLETADA"]
    fecha_oferta_utc: datetime | None = None
    fecha_respuesta_utc: datetime | None = None
    vuelo_propuesto: "TramoVueloResumen | None" = None


class TramoVueloResumen(BaseModel):
    """Datos de vuelo de un tramo, con el retraso y el OTP calculados (RN-01)."""

    id_detalle_reserva: int
    numero_secuencia: int
    numero_vuelo: str
    origen: AeropuertoResumen | None = None
    destino: AeropuertoResumen | None = None
    salida_programada_utc: datetime
    llegada_programada_utc: datetime
    salida_real_utc: datetime | None = None
    llegada_real_utc: datetime | None = None
    estado_vuelo: str | None = None
    estado_segmento: str
    clase_servicio: str
    clase_tarifaria: str | None = None
    numero_asiento: str | None = None
    monto_tarifa_pagada: Decimal
    moneda: str
    retraso_salida_min: int | None = None
    retraso_llegada_min: int | None = None
    es_otp: bool | None = None


class TramoItinerarioResponse(TramoVueloResumen):
    """Tramo del itinerario con reubicaciones propuestas."""

    reubicaciones: list[ReubicacionResumen] = Field(default_factory=list)


class ItinerarioResponse(BaseModel):
    """Itinerario del pasajero con sus tramos, conexiones y reubicaciones."""

    id_itinerario: int
    estado: str
    fecha_salida_utc: datetime
    fecha_creacion_utc: datetime
    fecha_actualizacion_utc: datetime
    tramos: list[TramoItinerarioResponse] = Field(default_factory=list)
    conexiones: list[ConexionResumen] = Field(default_factory=list)


class ReservaConItinerariosResponse(BaseModel):
    """Reserva del pasajero con todos sus itinerarios."""

    id_reserva: int
    codigo_reserva: str | None = None
    estado_reserva: str | None = None
    fecha_reserva_utc: datetime | None = None
    itinerarios: list[ItinerarioResponse] = Field(default_factory=list)


class PasajeroItinerariosResponse(BaseModel):
    """Respuesta de `GET /pasajeros/{id}/itinerarios`."""

    pasajero: PasajeroPerfilResponse
    reservas: list[ReservaConItinerariosResponse] = Field(default_factory=list)


# ── Compensaciones, pagos y notificaciones ────────────────────────────────


class NotificacionResumen(BaseModel):
    """Registro de la tabla `notificacion` (RN-09: trazabilidad del correo)."""

    model_config = ConfigDict(from_attributes=True)

    id_notificacion: int
    id_detalle_reserva: int
    id_evaluacion_conexion: int | None = None
    id_compensacion: int | None = None
    tipo: str
    canal: str
    estado_envio: Literal["PENDIENTE", "ENVIADA", "FALLIDA"]
    fecha_programada_utc: datetime
    fecha_envio_utc: datetime | None = None


class PagoResumen(BaseModel):
    """Pago asociado a una compensación (RN-09: máximo un pago por compensación)."""

    model_config = ConfigDict(from_attributes=True)

    id_pago: int
    clave_idempotencia: str
    id_transaccion_externa: str | None = None
    estado: Literal["PENDIENTE", "PAGADO", "RECHAZADO"]
    fecha_solicitud_utc: datetime
    fecha_actualizacion_utc: datetime


class CompensacionResumen(BaseModel):
    """Compensación calculada para un segmento del pasajero."""

    id_compensacion: int
    id_detalle_reserva: int
    id_incidencia: int
    id_regla_compensacion: int
    minutos_imputables: int | None = None
    monto: Decimal
    moneda: str
    fecha_calculo_utc: datetime
    estado: Literal["CALCULADA", "SOLICITADA", "PAGADA", "RECHAZADA", "ANULADA"]
    numero_vuelo: str | None = None
    pago: PagoResumen | None = None
    notificaciones: list[NotificacionResumen] = Field(default_factory=list)


class PasajeroCompensacionesResponse(BaseModel):
    """Respuesta de `GET /pasajeros/{id}/compensaciones`."""

    pasajero: PasajeroPerfilResponse
    compensaciones: list[CompensacionResumen] = Field(default_factory=list)
    resumen: "ResumenCompensaciones"


class ResumenCompensaciones(BaseModel):
    """Totales consolidados de las compensaciones del pasajero."""

    total_compensaciones: int = 0
    monto_total: Decimal = Decimal("0.00")
    moneda: str | None = None
    por_estado: dict[str, int] = Field(default_factory=dict)


# ── Consulta rápida por código de reserva ─────────────────────────────────


class ResumenEstadoReserva(BaseModel):
    """Totales del estado de una reserva."""

    total_vuelos: int = 0
    vuelos_afectados: int = 0
    conexiones_en_riesgo: int = 0
    reubicaciones_ofrecidas: int = 0
    total_compensaciones: int = 0
    monto_compensado: Decimal = Decimal("0.00")
    moneda: str | None = None


class ReservaEstadoResponse(BaseModel):
    """Respuesta de `GET /reservas/{codigo_reserva}/estado` (RN-11)."""

    id_reserva: int
    codigo_reserva: str
    estado_reserva: str
    fecha_reserva_utc: datetime
    fecha_actualizacion_utc: datetime
    itinerarios: list[ItinerarioResponse] = Field(default_factory=list)
    compensaciones: list[CompensacionResumen] = Field(default_factory=list)
    resumen: ResumenEstadoReserva


# Los modelos anteriores se referencian mutuamente; resolvemos los forward refs.
TramoVueloResumen.model_rebuild()
ReubicacionResumen.model_rebuild()
PasajeroCompensacionesResponse.model_rebuild()
