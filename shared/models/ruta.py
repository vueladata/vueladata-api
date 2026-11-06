from sqlalchemy import BigInteger, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class Ruta(Base):
    __tablename__ = "ruta"
    __table_args__ = (UniqueConstraint('id_aeropuerto_origen', 'id_aeropuerto_destino'), {"schema": "vueladata"})

    id_ruta: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_aeropuerto_origen: Mapped[int] = mapped_column(BigInteger)
    id_aeropuerto_destino: Mapped[int] = mapped_column(BigInteger)
    duracion_estimada_min: Mapped[int] = mapped_column(Integer)
