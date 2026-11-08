import os
import json
import boto3
from datetime import datetime, timezone
from pathlib import Path

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET = os.getenv("S3_BUCKET_BRONZE", "vueladata-datalake-bronze")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")  # Útil para LocalStack

# Inicialización segura y diferida del cliente S3 (no contacta AWS al importar).
_s3_client = None


def _cliente_s3():
    global _s3_client
    if _s3_client is None:
        boto3_kwargs = {"region_name": AWS_REGION}
        if AWS_ENDPOINT_URL:
            boto3_kwargs["endpoint_url"] = AWS_ENDPOINT_URL
        _s3_client = boto3.client("s3", **boto3_kwargs)
    return _s3_client

def subir_lote(mensajes: list, tipo: str = "eventos_oooi") -> str:
    """
    Sube un lote de mensajes crudos a S3 Bronze con particionamiento por fecha:
    bronze/{tipo}/year=YYYY/month=MM/day=DD/batch_HHMMSS_microseconds.json
    
    Si no hay conexión o credenciales de AWS y existe el flag LOCAL_LAKE_FALLBACK=true,
    persiste localmente en ./data/bronze/... para facilitar pruebas sin nube.
    """
    if not mensajes:
        return ""

    ahora = datetime.now(timezone.utc)
    clave = (
        f"bronze/{tipo}/"
        f"year={ahora.year}/month={ahora.month:02d}/day={ahora.day:02d}/"
        f"batch_{ahora.strftime('%H%M%S_%f')}.json"
    )
    contenido = json.dumps(mensajes, ensure_ascii=False, default=str, indent=2)

    try:
        _cliente_s3().put_object(
            Bucket=BUCKET,
            Key=clave,
            Body=contenido.encode("utf-8"),
            ContentType="application/json"
        )
        print(f"[Worker Lake] ☁️ Subidos {len(mensajes)} mensajes a s3://{BUCKET}/{clave}", flush=True)
        return clave
    except Exception as e:
        # Modo de contingencia local si se prueba sin credenciales AWS
        local_fallback = os.getenv("LOCAL_LAKE_FALLBACK", "true").lower() in ("true", "1", "yes")
        if local_fallback:
            ruta_local = Path("data") / clave
            ruta_local.parent.mkdir(parents=True, exist_ok=True)
            ruta_local.write_text(contenido, encoding="utf-8")
            print(f"[Worker Lake] 💾 S3 no disponible ({e}). Guardado localmente en {ruta_local}", flush=True)
            return str(ruta_local)
        else:
            raise e
