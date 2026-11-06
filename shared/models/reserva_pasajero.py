from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class ReservaPasajero(Base):
    __tablename__ = "reserva_pasajero"
    __table_args__ = (UniqueConstraint('id_reserva', 'id_pasajero'), {"schema": "vueladata"})

    id_reserva_pasajero: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_reserva: Mapped[int] = mapped_column(BigInteger)
    id_pasajero: Mapped[int] = mapped_column(BigInteger)
