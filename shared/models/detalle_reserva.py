from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.models.base import Base

if TYPE_CHECKING:  # solo para los type checkers; evita ciclos en tiempo de ejecución
    from shared.models.conexion_itinerario import ConexionItinerario
    from shared.models.evaluacion_conexion import EvaluacionConexion
    from shared.models.itinerario import Itinerario
    from shared.models.reubicacion import Reubicacion
    from shared.models.vuelo import Vuelo


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

    # Relaciones de lectura: existen para que la API cargue el grafo del pasajero con
    # selectinload/joinedload (RNF-04) en vez de una consulta por tramo (N+1).
    itinerario: Mapped["Itinerario"] = relationship(
        "Itinerario",
        primaryjoin="foreign(DetalleReserva.id_itinerario) == Itinerario.id_itinerario",
        viewonly=True,
    )
    vuelo: Mapped["Vuelo"] = relationship(
        "Vuelo",
        primaryjoin="foreign(DetalleReserva.id_vuelo) == Vuelo.id_vuelo",
        viewonly=True,
    )
    conexiones_salida: Mapped[list["ConexionItinerario"]] = relationship(
        "ConexionItinerario",
        primaryjoin="DetalleReserva.id_detalle_reserva == foreign(ConexionItinerario.id_detalle_reserva_salida)",
        viewonly=True,
    )
    reubicaciones: Mapped[list["Reubicacion"]] = relationship(
        "Reubicacion",
        primaryjoin="DetalleReserva.id_detalle_reserva == foreign(Reubicacion.id_detalle_reserva)",
        viewonly=True,
    )
