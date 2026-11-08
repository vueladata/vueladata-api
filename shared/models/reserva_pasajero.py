from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.itinerario import Itinerario


class ReservaPasajero(Base):
    __tablename__ = "reserva_pasajero"
    __table_args__ = (UniqueConstraint('id_reserva', 'id_pasajero'), {"schema": "vueladata"})

    id_reserva_pasajero: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_reserva: Mapped[int] = mapped_column(BigInteger)
    id_pasajero: Mapped[int] = mapped_column(BigInteger)

    # Relación de lectura reserva_pasajero -> itinerarios (RNF-04).
    itinerarios: Mapped[list["Itinerario"]] = relationship(
        "Itinerario",
        primaryjoin="ReservaPasajero.id_reserva_pasajero == foreign(Itinerario.id_reserva_pasajero)",
        order_by="Itinerario.fecha_salida_utc",
        viewonly=True,
    )
