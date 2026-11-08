from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.aeropuerto import Aeropuerto


class Ruta(Base):
    __tablename__ = "ruta"
    __table_args__ = (UniqueConstraint('id_aeropuerto_origen', 'id_aeropuerto_destino'), {"schema": "vueladata"})

    id_ruta: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_aeropuerto_origen: Mapped[int] = mapped_column(BigInteger)
    id_aeropuerto_destino: Mapped[int] = mapped_column(BigInteger)
    duracion_estimada_min: Mapped[int] = mapped_column(Integer)

    # Relaciones de lectura para la respuesta de la API (RNF-04: evitar N+1).
    aeropuerto_origen: Mapped["Aeropuerto"] = relationship(
        "Aeropuerto",
        primaryjoin="foreign(Ruta.id_aeropuerto_origen) == Aeropuerto.id_aeropuerto",
        viewonly=True,
    )
    aeropuerto_destino: Mapped["Aeropuerto"] = relationship(
        "Aeropuerto",
        primaryjoin="foreign(Ruta.id_aeropuerto_destino) == Aeropuerto.id_aeropuerto",
        viewonly=True,
    )
