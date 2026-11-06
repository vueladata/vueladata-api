from datetime import date
from sqlalchemy import BigInteger, Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class Pasajero(Base):
    __tablename__ = "pasajero"
    __table_args__ = (UniqueConstraint('tipo_documento', 'documento'), {"schema": "vueladata"})

    id_pasajero: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100))
    apellido: Mapped[str] = mapped_column(String(100))
    documento: Mapped[str] = mapped_column(String(50))
    tipo_documento: Mapped[str] = mapped_column(String(30))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    correo: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
