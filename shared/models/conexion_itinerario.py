from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.evaluacion_conexion import EvaluacionConexion


class ConexionItinerario(Base):
    __tablename__ = "conexion_itinerario"
    __table_args__ = (UniqueConstraint('id_detalle_reserva_llegada', 'id_detalle_reserva_salida'), {"schema": "vueladata"})

    id_conexion: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_regla_conexion: Mapped[int] = mapped_column(BigInteger)
    id_detalle_reserva_llegada: Mapped[int] = mapped_column(BigInteger)
    id_detalle_reserva_salida: Mapped[int] = mapped_column(BigInteger)

    # Relación de lectura conexión -> evaluaciones (RN-07 / RNF-04).
    evaluaciones: Mapped[list["EvaluacionConexion"]] = relationship(
        "EvaluacionConexion",
        primaryjoin="ConexionItinerario.id_conexion == foreign(EvaluacionConexion.id_conexion)",
        order_by="EvaluacionConexion.fecha_evaluacion_utc.desc()",
        viewonly=True,
    )
