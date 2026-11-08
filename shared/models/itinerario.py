from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.detalle_reserva import DetalleReserva
    from shared.models.reserva_pasajero import ReservaPasajero


class Itinerario(Base):
    __tablename__ = "itinerario"
    __table_args__ = {"schema": "vueladata"}

    id_itinerario: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_reserva_pasajero: Mapped[int] = mapped_column(BigInteger)
    fecha_salida_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(30))
    fecha_creacion_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_actualizacion_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relaciones de lectura itinerario -> tramos y -> reserva_pasajero (RNF-04).
    reserva_pasajero: Mapped["ReservaPasajero"] = relationship(
        "ReservaPasajero",
        primaryjoin="foreign(Itinerario.id_reserva_pasajero) == ReservaPasajero.id_reserva_pasajero",
        viewonly=True,
    )
    tramos: Mapped[list["DetalleReserva"]] = relationship(
        "DetalleReserva",
        primaryjoin="Itinerario.id_itinerario == foreign(DetalleReserva.id_itinerario)",
        order_by="DetalleReserva.numero_secuencia",
        viewonly=True,
    )
