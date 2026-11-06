from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class ConexionItinerario(Base):
    __tablename__ = "conexion_itinerario"
    __table_args__ = (UniqueConstraint('id_detalle_reserva_llegada', 'id_detalle_reserva_salida'), {"schema": "vueladata"})

    id_conexion: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_regla_conexion: Mapped[int] = mapped_column(BigInteger)
    id_detalle_reserva_llegada: Mapped[int] = mapped_column(BigInteger)
    id_detalle_reserva_salida: Mapped[int] = mapped_column(BigInteger)
