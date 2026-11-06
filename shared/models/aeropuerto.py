from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class Aeropuerto(Base):
    __tablename__ = "aeropuerto"
    __table_args__ = {"schema": "vueladata"}

    id_aeropuerto: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_ciudad: Mapped[int] = mapped_column(BigInteger)
    codigo_iata: Mapped[str] = mapped_column(String(3), unique=True)
    codigo_icao: Mapped[str | None] = mapped_column(String(4), unique=True, nullable=True)
    nombre: Mapped[str] = mapped_column(String(180))
    latitud: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    longitud: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    zona_horaria: Mapped[str] = mapped_column(String(64))
    es_hub: Mapped[bool] = mapped_column(Boolean)
