from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import (
    causas_router,
    compensaciones_router,
    eventos_pago_router,
    pagos_router,
    pasajeros_router,
    reglas_compensacion_router,
)

tags_metadata = [
    {
        "name": "Health",
        "description": "Verificación del estado del servicio y conectividad con PostgreSQL.",
    },
    {
        "name": "Pasajeros",
        "description": (
            "Consultas del pasajero sobre sus propias reservas, itinerarios, estado de vuelo "
            "y compensaciones (RF-06), con aislamiento por pasajero (RN-11)."
        ),
    },
    {
        "name": "Causas",
        "description": "Catálogo de causas normalizadas de incidencias operacionales (RN-03).",
    },
    {
        "name": "Reglas de Compensación",
        "description": "Políticas y escalas de compensación económica por retraso o cancelación (RN-05).",
    },
    {
        "name": "Compensaciones",
        "description": "Gestión de compensaciones calculadas para pasajeros y segmentos afectados (RN-09).",
    },
    {
        "name": "Pagos",
        "description": "Solicitudes de desembolso hacia la pasarela asíncrona F7 con clave de idempotencia.",
    },
    {
        "name": "Eventos de Pago",
        "description": "Historial y recepción de confirmaciones asíncronas de pago devueltas por F7.",
    },
]

app = FastAPI(
    title="API VuelaData - Módulo F7: Compensaciones y Pagos",
    description=(
        "API REST operacional de VuelaData para la gestión de incidencias, "
        "reglas de compensación, compensaciones a pasajeros y pasarela asíncrona de pagos (F7)."
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
)

# Inclusión de routers del dominio F7
app.include_router(pasajeros_router)
app.include_router(causas_router)
app.include_router(reglas_compensacion_router)
app.include_router(compensaciones_router)
app.include_router(pagos_router)
app.include_router(eventos_pago_router)


@app.get(
    "/health",
    tags=["Health"],
    summary="Verificar salud de la API",
    status_code=status.HTTP_200_OK,
)
def health():
    """Confirma que el servicio FastAPI está activo y respondiendo peticiones."""
    return {"status": "ok"}


@app.get(
    "/health/db",
    tags=["Health"],
    summary="Verificar conexión a la base de datos",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Base de datos conectada correctamente"},
        503: {"description": "No se pudo conectar con la base de datos"},
    },
)
def health_db(db: Session = Depends(get_db)):
    """Ejecuta una consulta liviana contra PostgreSQL para comprobar la disponibilidad del motor relacional."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "online"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo conectar con la base de datos",
        )