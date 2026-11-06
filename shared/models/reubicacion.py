from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class Reubicacion(Base):
    __tablename__ = "reubicacion"
    __table_args__ = {"schema": "vueladata"}

    id_reubicacion: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_detalle_reserva: Mapped[int] = mapped_column(BigInteger)
    id_incidencia: Mapped[int] = mapped_column(BigInteger)
    id_vuelo_propuesto: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estado: Mapped[str] = mapped_column(String(30))
    fecha_oferta_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_respuesta_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
