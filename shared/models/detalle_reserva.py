from decimal import Decimal
from sqlalchemy import BigInteger, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class DetalleReserva(Base):
    __tablename__ = "detalle_reserva"
    __table_args__ = (UniqueConstraint('id_vuelo', 'numero_asiento'), UniqueConstraint('id_itinerario', 'numero_secuencia'), {"schema": "vueladata"})

    id_detalle_reserva: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_itinerario: Mapped[int] = mapped_column(BigInteger)
    id_vuelo: Mapped[int] = mapped_column(BigInteger)
    numero_secuencia: Mapped[int] = mapped_column(Integer)
    clase_servicio: Mapped[str] = mapped_column(String(40))
    clase_tarifaria: Mapped[str | None] = mapped_column(String(20), nullable=True)
    monto_tarifa_pagada: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    moneda: Mapped[str] = mapped_column(String(3))
    numero_asiento: Mapped[str | None] = mapped_column(String(10), nullable=True)
    estado_segmento: Mapped[str] = mapped_column(String(30))
