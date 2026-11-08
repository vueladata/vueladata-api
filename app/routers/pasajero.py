"""Endpoints HTTP de consulta para pasajeros (RF-06).

Cumplen:
- RF-06: exponer el estado de vuelo y de compensación al pasajero.
- RN-11: un pasajero solo puede consultar sus propias reservas, itinerarios y
  compensaciones. La identidad llega en la cabecera `X-Pasajero-Id` (validada
  contra el recurso solicitado); si falta, se responde 401 y si no coincide 403.
- RNF-04: las consultas cargan el grafo completo con eager loading (ver app/crud/pasajeros.py).
"""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import pasajeros as crud_pasajeros
from app.database import get_db
from app.schemas.pasajero_consulta import (
    PasajeroCompensacionesResponse,
    PasajeroItinerariosResponse,
    PasajeroPerfilResponse,
    ReservaEstadoResponse,
)

router = APIRouter(tags=["Pasajeros"])


# ── RN-11: identidad del solicitante ──────────────────────────────────────


def id_pasajero_solicitante(
    x_pasajero_id: int | None = Header(
        default=None,
        alias="X-Pasajero-Id",
        description="Identificador del pasajero autenticado (RN-11).",
    ),
) -> int:
    """Devuelve el id del pasajero que realiza la consulta."""
    if x_pasajero_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta la cabecera X-Pasajero-Id para identificar al pasajero (RN-11).",
        )
    return x_pasajero_id


def verificar_privacidad(id_recurso: int, id_solicitante: int) -> None:
    """RN-11: el recurso solicitado debe pertenecer al pasajero autenticado."""
    if id_recurso != id_solicitante:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un pasajero solo puede consultar sus propias reservas, itinerarios y compensaciones (RN-11).",
        )


def _404_pasajero(id_pasajero: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Pasajero con id {id_pasajero} no fue encontrado",
    )


# ── Perfil ────────────────────────────────────────────────────────────────


@router.get(
    "/pasajeros/{id_pasajero}",
    response_model=PasajeroPerfilResponse,
    status_code=status.HTTP_200_OK,
    summary="Perfil básico del pasajero",
    description="Devuelve los datos de identificación y contacto del pasajero (RF-06).",
    responses={
        401: {"description": "Falta la cabecera X-Pasajero-Id"},
        403: {"description": "El pasajero intenta consultar el perfil de otro (RN-11)"},
        404: {"description": "Pasajero no encontrado"},
    },
)
def read_pasajero(
    id_pasajero: int,
    id_solicitante: int = Depends(id_pasajero_solicitante),
    db: Session = Depends(get_db),
):
    verificar_privacidad(id_pasajero, id_solicitante)

    pasajero = crud_pasajeros.get_pasajero(db, id_pasajero)
    if pasajero is None:
        raise _404_pasajero(id_pasajero)
    return pasajero


# ── Reservas e itinerarios con vuelos ─────────────────────────────────────


@router.get(
    "/pasajeros/{id_pasajero}/itinerarios",
    response_model=PasajeroItinerariosResponse,
    status_code=status.HTTP_200_OK,
    summary="Reservas e itinerarios del pasajero",
    description=(
        "Devuelve las reservas e itinerarios propios del pasajero con sus tramos y vuelos: "
        "estado actual, retrasos calculados (RN-01), evaluaciones de conexión (RN-07) "
        "y propuestas de reubicación (RN-05/RN-06)."
    ),
    responses={
        401: {"description": "Falta la cabecera X-Pasajero-Id"},
        403: {"description": "El pasajero intenta consultar los itinerarios de otro (RN-11)"},
        404: {"description": "Pasajero no encontrado"},
    },
)
def read_pasajero_itinerarios(
    id_pasajero: int,
    id_solicitante: int = Depends(id_pasajero_solicitante),
    db: Session = Depends(get_db),
):
    verificar_privacidad(id_pasajero, id_solicitante)

    datos = crud_pasajeros.itinerarios_pasajero(db, id_pasajero)
    if datos is None:
        raise _404_pasajero(id_pasajero)
    return datos


@router.get(
    "/pasajeros/{id_pasajero}/reservas",
    response_model=PasajeroItinerariosResponse,
    status_code=status.HTTP_200_OK,
    summary="Reservas del pasajero (alias de /itinerarios)",
    description="Misma información que `/pasajeros/{id_pasajero}/itinerarios`, con las reservas como nivel superior.",
    include_in_schema=True,
    responses={
        401: {"description": "Falta la cabecera X-Pasajero-Id"},
        403: {"description": "El pasajero intenta consultar las reservas de otro (RN-11)"},
        404: {"description": "Pasajero no encontrado"},
    },
)
def read_pasajero_reservas(
    id_pasajero: int,
    id_solicitante: int = Depends(id_pasajero_solicitante),
    db: Session = Depends(get_db),
):
    verificar_privacidad(id_pasajero, id_solicitante)

    datos = crud_pasajeros.itinerarios_pasajero(db, id_pasajero)
    if datos is None:
        raise _404_pasajero(id_pasajero)
    return datos


# ── Compensaciones, pagos y notificaciones ────────────────────────────────


@router.get(
    "/pasajeros/{id_pasajero}/compensaciones",
    response_model=PasajeroCompensacionesResponse,
    status_code=status.HTTP_200_OK,
    summary="Compensaciones, pagos y notificaciones del pasajero",
    description=(
        "Devuelve exclusivamente las compensaciones del pasajero, con el estado de su pago "
        "(RN-09) y las notificaciones asociadas (`vueladata.notificacion`), más un resumen consolidado."
    ),
    responses={
        401: {"description": "Falta la cabecera X-Pasajero-Id"},
        403: {"description": "El pasajero intenta consultar las compensaciones de otro (RN-11)"},
        404: {"description": "Pasajero no encontrado"},
    },
)
def read_pasajero_compensaciones(
    id_pasajero: int,
    id_solicitante: int = Depends(id_pasajero_solicitante),
    db: Session = Depends(get_db),
):
    verificar_privacidad(id_pasajero, id_solicitante)

    datos = crud_pasajeros.compensaciones_pasajero(db, id_pasajero)
    if datos is None:
        raise _404_pasajero(id_pasajero)
    return datos


# ── Consulta rápida por código de reserva ─────────────────────────────────


@router.get(
    "/reservas/{codigo_reserva}/estado",
    response_model=ReservaEstadoResponse,
    status_code=status.HTTP_200_OK,
    summary="Estado rápido de una reserva del pasajero",
    description=(
        "Consulta rápida del estado de vuelo y de compensación de una reserva por su código. "
        "Verifica que la reserva pertenezca al pasajero autenticado (RN-11)."
    ),
    responses={
        401: {"description": "Falta la cabecera X-Pasajero-Id"},
        403: {"description": "La reserva pertenece a otro pasajero (RN-11)"},
        404: {"description": "Reserva no encontrada"},
    },
)
def read_estado_reserva(
    codigo_reserva: str,
    id_solicitante: int = Depends(id_pasajero_solicitante),
    db: Session = Depends(get_db),
):
    reserva = crud_pasajeros.get_reserva_por_codigo(db, codigo_reserva)
    if reserva is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reserva con código '{codigo_reserva}' no fue encontrada",
        )

    es_dueno = crud_pasajeros.pasajero_tiene_reserva(db, reserva.id_reserva, id_solicitante)
    if not es_dueno:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un pasajero solo puede consultar sus propias reservas, itinerarios y compensaciones (RN-11).",
        )

    datos = crud_pasajeros.estado_reserva(db, reserva.id_reserva, id_solicitante)
    if datos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reserva con código '{codigo_reserva}' no fue encontrada",
        )
    return datos
