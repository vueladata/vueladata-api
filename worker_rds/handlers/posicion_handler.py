import json
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from shared.models.posicion_aeronave import PosicionAeronave
from shared.models.aeronave import Aeronave
from sqlalchemy import func

def procesar_posicion_aeronave(body: bytes | str | dict, db: Session) -> str:
    """
    Procesa un mensaje de telemetría/posición de aeronave proveniente de OpenSky (Lambda F2).
    
    Retorna:
      - 'ok': persistido con éxito.
      - 'duplicado': ya registrado (idempotencia por id_externo_posicion).
      - 'invalido': faltan campos obligatorios o coordenadas no válidas.
    """
    if isinstance(body, (bytes, str)):
        data = json.loads(body)
    else:
        data = body

    id_externo = data.get("id_externo_posicion")
    lat = data.get("latitud")
    lon = data.get("longitud")
    id_aeronave = data.get("id_aeronave")
    if id_aeronave is None:
        code = data.get("codigo_icao24")
        aircraft = (db.query(Aeronave).filter(func.lower(Aeronave.codigo_icao24) == str(code).lower()).first()
                    if code else None)
        if aircraft is None:
            return "sin_catalogo"
        id_aeronave = aircraft.id_aeronave

    if not id_externo or lat is None or lon is None:
        return "invalido"

    # 1. Conversión de fecha y validación de coordenadas
    try:
        lat_dec = Decimal(str(lat))
        lon_dec = Decimal(str(lon))

        # Validación de rango geográfico básico
        if not (-90 <= lat_dec <= 90) or not (-180 <= lon_dec <= 180):
            return "invalido"

        fecha_pos_raw = data.get("fecha_hora_posicion_utc")
        if fecha_pos_raw:
            fecha_pos = datetime.fromisoformat(str(fecha_pos_raw))
            if fecha_pos.tzinfo is None:
                fecha_pos = fecha_pos.replace(tzinfo=timezone.utc)
        else:
            fecha_pos = datetime.now(timezone.utc)
    except Exception:
        return "invalido"

    # 2. Idempotencia
    existente = (
        db.query(PosicionAeronave)
        .filter_by(id_externo_posicion=str(id_externo))
        .first()
    )
    if existente:
        return "duplicado"

    ahora_utc = datetime.now(timezone.utc)

    # 3. Insertar registro
    nueva_posicion = PosicionAeronave(
        id_aeronave=int(id_aeronave),
        fecha_hora_posicion_utc=fecha_pos,
        fecha_hora_recepcion_utc=ahora_utc,
        latitud=lat_dec,
        longitud=lon_dec,
        altitud_m=Decimal(str(data["altitud_m"])) if data.get("altitud_m") is not None else None,
        velocidad_kmh=Decimal(str(data["velocidad_kmh"])) if data.get("velocidad_kmh") is not None else None,
        rumbo_grados=Decimal(str(data["rumbo_grados"])) if data.get("rumbo_grados") is not None else None,
        en_tierra=bool(data.get("en_tierra", False)),
        id_externo_posicion=str(id_externo)
    )
    db.add(nueva_posicion)
    db.commit()
    return "ok"
