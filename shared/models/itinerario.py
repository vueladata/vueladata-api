from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class Itinerario(Base):
    __tablename__ = "itinerario"
    __table_args__ = {"schema": "vueladata"}

    id_itinerario: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_reserva_pasajero: Mapped[int] = mapped_column(BigInteger)
    fecha_salida_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(30))
    fecha_creacion_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_actualizacion_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
