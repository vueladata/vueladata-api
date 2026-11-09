import json
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from shared.models.observacion_clima import ObservacionClima
from shared.models.aeropuerto import Aeropuerto
from worker_rds.business_rules import evaluar_condiciones_adversas

def procesar_observacion_clima(body: bytes | str | dict, db: Session) -> str:
    """
    Procesa una observación meteorológica horaria de Open-Meteo (Lambda F3).
    Aplica RN-04 para detección de condiciones climáticas adversas.
    
    Retorna:
      - 'ok': persistido con éxito.
      - 'duplicado': ya existe una observación para ese aeropuerto y hora.
      - 'invalido': datos incompletos o timestamp erróneo.
    """
    if isinstance(body, (bytes, str)):
        data = json.loads(body)
    else:
        data = body

    id_aeropuerto = data.get("id_aeropuerto")
    fecha_obs_raw = data.get("fecha_hora_observacion_utc")

    if not id_aeropuerto or not fecha_obs_raw:
        return "invalido"

    if not str(id_aeropuerto).isdigit():
        airport = db.query(Aeropuerto).filter_by(codigo_iata=str(data.get("codigo_iata") or id_aeropuerto).upper()).first()
        if airport is None:
            return "sin_catalogo"
        id_aeropuerto = airport.id_aeropuerto

    try:
        fecha_obs = datetime.fromisoformat(str(fecha_obs_raw))
        if fecha_obs.tzinfo is None:
            fecha_obs = fecha_obs.replace(tzinfo=timezone.utc)
    except Exception:
        return "invalido"

    # 1. Idempotencia basada en la restricción única (id_aeropuerto, fecha_hora_observacion_utc)
    existente = (
        db.query(ObservacionClima)
        .filter_by(id_aeropuerto=int(id_aeropuerto), fecha_hora_observacion_utc=fecha_obs)
        .first()
    )
    if existente:
        return "duplicado"

    ahora_utc = datetime.now(timezone.utc)
    visib = Decimal(str(data["visibilidad_km"])) if data.get("visibilidad_km") is not None else None
    viento = Decimal(str(data["velocidad_viento_kmh"])) if data.get("velocidad_viento_kmh") is not None else None
    codigo_clima = data.get("codigo_clima")

    # 2. RN-04: Evaluar condiciones adversas
    es_adversa = evaluar_condiciones_adversas(
        velocidad_viento_kmh=viento,
        visibilidad_km=visib,
        codigo_clima=codigo_clima
    )
    if es_adversa:
        print(f"[Worker RDS] ⚠️ Condición climática adversa detectada en Aeropuerto {id_aeropuerto} (Viento: {viento} km/h, Visib: {visib} km)", flush=True)

    # 3. Persistir observación
    nueva_obs = ObservacionClima(
        id_aeropuerto=int(id_aeropuerto),
        fecha_hora_observacion_utc=fecha_obs,
        fecha_hora_recepcion_utc=ahora_utc,
        visibilidad_km=visib,
        velocidad_viento_kmh=viento,
        direccion_viento_grados=Decimal(str(data["direccion_viento_grados"])) if data.get("direccion_viento_grados") is not None else None,
        temperatura_c=Decimal(str(data["temperatura_c"])) if data.get("temperatura_c") is not None else None,
        precipitacion_mm=Decimal(str(data["precipitacion_mm"])) if data.get("precipitacion_mm") is not None else None,
        codigo_clima=codigo_clima
    )
    db.add(nueva_obs)
    db.commit()
    return "ok"
