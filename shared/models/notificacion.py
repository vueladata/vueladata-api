from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class Notificacion(Base):
    __tablename__ = "notificacion"
    __table_args__ = {"schema": "vueladata"}

    id_notificacion: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_detalle_reserva: Mapped[int] = mapped_column(BigInteger)
    id_evaluacion_conexion: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    id_compensacion: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tipo: Mapped[str] = mapped_column(String(30))
    canal: Mapped[str] = mapped_column(String(20))
    estado_envio: Mapped[str] = mapped_column(String(30))
    fecha_programada_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_envio_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
