from datetime import date
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.reserva_pasajero import ReservaPasajero


class Pasajero(Base):
    __tablename__ = "pasajero"
    __table_args__ = (UniqueConstraint('tipo_documento', 'documento'), {"schema": "vueladata"})

    id_pasajero: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100))
    apellido: Mapped[str] = mapped_column(String(100))
    documento: Mapped[str] = mapped_column(String(50))
    tipo_documento: Mapped[str] = mapped_column(String(30))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    correo: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Relaciones de lectura del grafo pasajero -> reserva -> itinerario -> tramo (RNF-04).
    reservas: Mapped[list["ReservaPasajero"]] = relationship(
        "ReservaPasajero",
        primaryjoin="Pasajero.id_pasajero == foreign(ReservaPasajero.id_pasajero)",
        viewonly=True,
    )
