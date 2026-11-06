"""Consultas a la base que necesita el worker de correos."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from shared.models.aeropuerto import Aeropuerto
from shared.models.detalle_reserva import DetalleReserva
from shared.models.itinerario import Itinerario
from shared.models.pasajero import Pasajero
from shared.models.reserva_pasajero import ReservaPasajero
from shared.models.ruta import Ruta
from shared.models.vuelo import Vuelo


@dataclass
class InfoVuelo:
    """Datos de un vuelo listos para mostrar en un correo.

    salida y llegada están en la hora local de cada aeropuerto (RN-02).
    """

    numero_vuelo: str
    origen: str  # código IATA, ej. "MDE"
    destino: str
    salida: datetime  # hora local del aeropuerto de origen
    llegada: datetime  # hora local del aeropuerto de destino
    origen_nombre: str = ""  # ej. "José María Córdova"
    destino_nombre: str = ""

    @property
    def salida_local(self) -> str:
        return self.salida.strftime("%d/%m/%Y %H:%M")

    @property
    def llegada_local(self) -> str:
        return self.llegada.strftime("%d/%m/%Y %H:%M")

    def con_retraso(self, minutos: int) -> "InfoVuelo":
        """El mismo vuelo con la salida y la llegada corridas por el retraso."""
        return replace(self, salida=self.salida + timedelta(minutes=minutos),
                       llegada=self.llegada + timedelta(minutes=minutos))


def en_utc(fecha: datetime) -> datetime:
    """Si la fecha viene sin zona horaria, sabemos que está guardada en UTC."""
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha


def a_hora_local(fecha_utc: datetime, zona_horaria: str) -> datetime:
    return en_utc(fecha_utc).astimezone(ZoneInfo(zona_horaria))


def describir_vuelo(db: Session, id_vuelo: int) -> InfoVuelo | None:
    vuelo = db.query(Vuelo).filter_by(id_vuelo=id_vuelo).first()
    if vuelo is None:
        return None
    ruta = db.query(Ruta).filter_by(id_ruta=vuelo.id_ruta).first()
    origen = db.query(Aeropuerto).filter_by(id_aeropuerto=ruta.id_aeropuerto_origen).first()
    destino = db.query(Aeropuerto).filter_by(id_aeropuerto=ruta.id_aeropuerto_destino).first()
    return InfoVuelo(
        numero_vuelo=vuelo.numero_vuelo,
        origen=origen.codigo_iata,
        destino=destino.codigo_iata,
        salida=a_hora_local(vuelo.salida_programada_utc, origen.zona_horaria),
        llegada=a_hora_local(vuelo.llegada_programada_utc, destino.zona_horaria),
        origen_nombre=origen.nombre,
        destino_nombre=destino.nombre,
    )


def pasajeros_del_vuelo(db: Session, id_vuelo: int) -> list[tuple[DetalleReserva, Pasajero]]:
    """Cada pasajero del vuelo con su tramo: detalle_reserva -> itinerario -> reserva_pasajero -> pasajero."""
    return (
        db.query(DetalleReserva, Pasajero)
        .join(Itinerario, DetalleReserva.id_itinerario == Itinerario.id_itinerario)
        .join(ReservaPasajero, Itinerario.id_reserva_pasajero == ReservaPasajero.id_reserva_pasajero)
        .join(Pasajero, ReservaPasajero.id_pasajero == Pasajero.id_pasajero)
        .filter(DetalleReserva.id_vuelo == id_vuelo)
        .order_by(DetalleReserva.id_detalle_reserva)
        .all()
    )


def pasajero_del_tramo(db: Session, id_detalle_reserva: int) -> tuple[DetalleReserva, Pasajero] | None:
    return (
        db.query(DetalleReserva, Pasajero)
        .join(Itinerario, DetalleReserva.id_itinerario == Itinerario.id_itinerario)
        .join(ReservaPasajero, Itinerario.id_reserva_pasajero == ReservaPasajero.id_reserva_pasajero)
        .join(Pasajero, ReservaPasajero.id_pasajero == Pasajero.id_pasajero)
        .filter(DetalleReserva.id_detalle_reserva == id_detalle_reserva)
        .first()
    )
