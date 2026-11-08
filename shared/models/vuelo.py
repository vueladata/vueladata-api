from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.estado_vuelo import EstadoVuelo
    from shared.models.ruta import Ruta

class Vuelo(Base):
    __tablename__ = "vuelo"
    __table_args__ = (UniqueConstraint('numero_vuelo', 'salida_programada_utc'), {"schema": "vueladata"})

    id_vuelo: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_ruta: Mapped[int] = mapped_column(BigInteger)
    id_aeronave: Mapped[int] = mapped_column(BigInteger)
    numero_vuelo: Mapped[str] = mapped_column(String(12))
    salida_programada_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    llegada_programada_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    salida_real_puerta_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    despegue_real_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aterrizaje_real_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    llegada_real_puerta_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    id_estado_vuelo_actual: Mapped[int] = mapped_column(SmallInteger)
    id_aeropuerto_desvio: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Relaciones de lectura para armar la respuesta de la API sin N+1 (RNF-04).
    ruta: Mapped["Ruta"] = relationship(
        "Ruta",
        primaryjoin="foreign(Vuelo.id_ruta) == Ruta.id_ruta",
        viewonly=True,
    )
    estado_actual: Mapped["EstadoVuelo"] = relationship(
        "EstadoVuelo",
        primaryjoin="foreign(Vuelo.id_estado_vuelo_actual) == EstadoVuelo.id_estado_vuelo",
        viewonly=True,
    )
