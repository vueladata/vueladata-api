import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from shared.models.causa import Causa
from shared.models.observacion_clima import ObservacionClima
from shared.models.ruta import Ruta

# Catálogo conocido de causas válidas
CAUSAS_CONOCIDAS = {
    "TECNICA": {"id_causa": 1, "es_imputable": True, "nombre": "Falla técnica de aeronave"},
    "TRIPULACION": {"id_causa": 2, "es_imputable": True, "nombre": "Falta o descanso de tripulación"},
    "OPERACIONAL": {"id_causa": 3, "es_imputable": True, "nombre": "Problemas operacionales internos"},
    "CLIMA": {"id_causa": 4, "es_imputable": False, "nombre": "Condiciones meteorológicas adversas"},
}

# RN-01: un vuelo es puntual si el retraso de llegada es menor o igual a 15 minutos.
UMBRAL_OTP_MINUTOS = 15

# RN-04: umbrales de auditoría climática.
VIENTO_ADVERSO_KMH = 50.0
VISIBILIDAD_ADVERSA_KM = 1.0
VENTANA_CLIMA_HORAS = 1

# RN-05: escala de compensación por retraso imputable.
RETRASO_MINIMO_COMPENSACION_MIN = 120  # 2 horas
RETRASO_TRAMO_25_MIN = 240  # 4 horas
RETRASO_TRAMO_50_MIN = 360  # 6 horas
AVISO_CANCELACION_72H = 72

# RN-08: tiempos mínimos de rotación por tipo de vuelo.
ROTACION_NACIONAL_MIN = 45
ROTACION_INTERNACIONAL_MIN = 60


def resolver_causa(codigo_causa: Optional[str], db: Optional[Session] = None) -> tuple[Optional[int], bool, bool]:
    """
    RN-03: Clasifica la causa del evento.
    Retorna: (id_causa, es_imputable, es_valida)
    """
    if not codigo_causa:
        return None, False, True

    codigo_upper = codigo_causa.strip().upper()

    # Si es un código de error de caos como ERROR_99
    if codigo_upper.startswith("ERROR") or codigo_upper == "INVALIDA":
        return None, False, False

    # Intentar buscar en la base de datos si la sesión está disponible
    if db is not None:
        try:
            causa_db = db.query(Causa).filter_by(codigo=codigo_upper).first()
            if causa_db:
                return causa_db.id_causa, bool(causa_db.es_imputable), True
        except Exception:
            pass  # Fallback al catálogo en memoria

    # Búsqueda en catálogo base conocido
    if codigo_upper in CAUSAS_CONOCIDAS:
        c = CAUSAS_CONOCIDAS[codigo_upper]
        return c["id_causa"], c["es_imputable"], True

    return None, False, False


def es_otp(retraso_llegada_min: Optional[int]) -> Optional[bool]:
    """RN-01: puntual si el retraso de llegada es <= 15 minutos.

    Devuelve `None` cuando el vuelo aún no tiene llegada real (no se puede calcular).
    """
    if retraso_llegada_min is None:
        return None
    return retraso_llegada_min <= UMBRAL_OTP_MINUTOS


def evaluar_condiciones_adversas(
    velocidad_viento_kmh: Optional[float | Decimal] = None,
    visibilidad_km: Optional[float | Decimal] = None,
    codigo_clima: Optional[str] = None
) -> bool:
    """
    RN-04: Evalúa si existen condiciones climáticas adversas en la zona.
    Condiciones:
    - Viento superior a 50 km/h
    - Visibilidad menor a 1.0 km
    - Códigos climáticos extremos (TORMENTA, HURACAN, NIEBLA_DENSA)
    """
    if velocidad_viento_kmh is not None and float(velocidad_viento_kmh) > VIENTO_ADVERSO_KMH:
        return True
    if visibilidad_km is not None and float(visibilidad_km) < VISIBILIDAD_ADVERSA_KM:
        return True
    if codigo_clima:
        clima_upper = codigo_clima.upper()
        if any(w in clima_upper for w in ("TORMENTA", "HURACAN", "STORM", "FOG", "NIEBLA")):
            return True
    return False


def _en_utc(fecha: datetime) -> datetime:
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha


def _observacion_adversa(
    db: Session, id_aeropuerto: int, centro: datetime, desde: datetime, hasta: datetime
) -> ObservacionClima | None:
    """Observación adversa del aeropuerto más cercana a la hora del evento."""
    observaciones = (
        db.query(ObservacionClima)
        .filter(
            ObservacionClima.id_aeropuerto == id_aeropuerto,
            ObservacionClima.fecha_hora_observacion_utc >= desde,
            ObservacionClima.fecha_hora_observacion_utc <= hasta,
        )
        .all()
    )
    adversas = [
        obs
        for obs in observaciones
        # RN-04 solo considera viento y visibilidad (no cualquier código climático).
        if evaluar_condiciones_adversas(
            velocidad_viento_kmh=obs.velocidad_viento_kmh,
            visibilidad_km=obs.visibilidad_km,
        )
    ]
    if not adversas:
        return None
    return min(adversas, key=lambda obs: abs((_en_utc(obs.fecha_hora_observacion_utc) - centro).total_seconds()))


def evaluar_auditoria_climatica(
    db: Session,
    id_ruta: Optional[int],
    fecha_evento: datetime,
    codigo_causa: Optional[str],
) -> tuple[bool, Optional[int], Optional[int]]:
    """RN-04: decide si una causa técnica requiere auditoría climática.

    Retorna `(requiere_auditoria, id_observacion_origen, id_observacion_destino)`.
    Solo aplica a causas reportadas como "TECNICA"; exige clima adverso (viento
    > 50 km/h o visibilidad < 1 km) en origen o destino dentro de una hora del evento.
    """
    if not codigo_causa or codigo_causa.strip().upper() != "TECNICA" or id_ruta is None:
        return False, None, None

    ruta = db.query(Ruta).filter_by(id_ruta=id_ruta).first()
    if ruta is None:
        return False, None, None

    fecha = _en_utc(fecha_evento)
    desde = fecha - timedelta(hours=VENTANA_CLIMA_HORAS)
    hasta = fecha + timedelta(hours=VENTANA_CLIMA_HORAS)

    obs_origen = _observacion_adversa(db, ruta.id_aeropuerto_origen, fecha, desde, hasta)
    obs_destino = _observacion_adversa(db, ruta.id_aeropuerto_destino, fecha, desde, hasta)

    if obs_origen is None and obs_destino is None:
        return False, None, None

    return (
        True,
        obs_origen.id_observacion_clima if obs_origen else None,
        obs_destino.id_observacion_clima if obs_destino else None,
    )


def calcular_porcentaje_compensacion(
    minutos_retraso: int,
    es_imputable: bool,
    es_cancelacion: bool = False,
    horas_aviso: Optional[float] = None,
) -> Decimal:
    """RN-05: porcentaje de compensación según minutos de retraso e imputabilidad.

    Escala obligatoria para retrasos imputables:
    - 2 a 4 horas  -> 25 %
    - 4 a 6 horas  -> 50 %
    - 6 horas o más -> 100 %

    Una cancelación imputable avisada con menos de 72 horas también es 100 %.
    RN-06: las causas no imputables siempre pagan 0 %.
    """
    if not es_imputable:
        return Decimal("0.00")

    if es_cancelacion:
        if horas_aviso is None or horas_aviso < AVISO_CANCELACION_72H:
            return Decimal("100.00")
        return Decimal("0.00")

    if minutos_retraso < RETRASO_MINIMO_COMPENSACION_MIN:
        return Decimal("0.00")
    if minutos_retraso < RETRASO_TRAMO_25_MIN:
        return Decimal("25.00")
    if minutos_retraso < RETRASO_TRAMO_50_MIN:
        return Decimal("50.00")
    return Decimal("100.00")


def minutos_rotacion(tipo_vuelo: Optional[str]) -> int:
    """RN-08: 45 minutos para vuelos nacionales y 60 para internacionales."""
    if tipo_vuelo and tipo_vuelo.strip().upper() in ("INTERNACIONAL", "INTERNATIONAL"):
        return ROTACION_INTERNACIONAL_MIN
    return ROTACION_NACIONAL_MIN


def calcular_retraso_propagado(minutos_retraso: int, tipo_vuelo: Optional[str]) -> int:
    """RN-08: retraso que hereda el siguiente vuelo de la misma matrícula.

    Al retraso del vuelo anterior se le descuenta el tiempo mínimo de rotación
    (45 min nacional / 60 min internacional). Nunca es negativo.
    """
    return max(0, int(minutos_retraso) - minutos_rotacion(tipo_vuelo))


def generar_clave_idempotencia(id_vuelo: int, id_pasajero: int, id_evento: int) -> str:
    """
    RN-09: Genera una clave hash única e idempotente para evitar compensaciones duplicadas.
    """
    raw = f"{id_vuelo}:{id_pasajero}:{id_evento}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generar_clave_idempotencia_segmento(id_detalle_reserva: int, id_pasajero: int) -> str:
    """RN-09: una sola compensación por pasajero y segmento de vuelo.

    La clave depende del segmento (no del evento) para que varios eventos repetidos
    del mismo vuelo no generen pagos distintos para el mismo pasajero.
    """
    raw = f"segmento:{id_detalle_reserva}:{id_pasajero}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
