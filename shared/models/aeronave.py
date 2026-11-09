"""Minimal read mapping for resolving OpenSky ICAO24 against the real fleet."""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.base import Base


class Aeronave(Base):
    __tablename__ = 'aeronave'
    __table_args__ = {'schema': 'vueladata'}
    id_aeronave: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo_icao24: Mapped[str | None] = mapped_column(String(6), unique=True, nullable=True)
