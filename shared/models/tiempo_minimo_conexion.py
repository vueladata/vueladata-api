from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class TiempoMinimoConexion(Base):
    __tablename__ = "tiempo_minimo_conexion"
    __table_args__ = (UniqueConstraint('id_aeropuerto', 'tipo_llegada', 'tipo_salida', 'vigente_desde_utc'), {"schema": "vueladata"})

    id_regla_conexion: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_aeropuerto: Mapped[int] = mapped_column(BigInteger)
    tipo_llegada: Mapped[str] = mapped_column(String(20))
    tipo_salida: Mapped[str] = mapped_column(String(20))
    minutos_minimos: Mapped[int] = mapped_column(Integer)
    vigente_desde_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vigente_hasta_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
