from app.routers.causa import router as causas_router
from app.routers.regla_compensacion import router as reglas_compensacion_router
from app.routers.compensacion import router as compensaciones_router
from app.routers.pago import router as pagos_router
from app.routers.evento_pago import router as eventos_pago_router
from app.routers.pasajero import router as pasajeros_router

__all__ = [
    "causas_router",
    "reglas_compensacion_router",
    "compensaciones_router",
    "pagos_router",
    "eventos_pago_router",
    "pasajeros_router",
]
