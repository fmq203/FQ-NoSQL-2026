"""Endpoint POST /api/reservar - inicia la SAGA completa de compra de entradas."""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from src.chain.builder import ChainBuilder
from src.models.reserva import ReservaContext, ReservaCreateRequest, ReservaResponse, RFC7807Error
from src.services.mongo import get_reservas_collection
from src.services.saga_orchestrator import (
    SagaOrchestrator,
    compensate_step_4_payment,
    compensate_step_5_reservation,
)
from src.utils.errors import EventFlowHTTPException
from src.utils.idempotency import check_idempotency

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reservas"])

_ERROR_CODE_BY_STATUS = {
    400: "VALIDATION_ERROR",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _raise_from_context(context: ReservaContext, instance: str) -> None:
    """Traduce el resultado de la cadena a un EventFlowHTTPException RFC 7807.

    Usa context.error_code (seteado por el handler que detecto el fallo,
    ej. USER_NOT_FOUND, INSUFFICIENT_INVENTORY) cuando esta disponible, para
    que el `type` URI identifique la causa real en vez de solo el status
    HTTP. Si algun paso no lo setea explicitamente, cae al mapeo generico
    por status_code.
    """
    status_code = context.status_code or 500
    error_code = context.error_code or _ERROR_CODE_BY_STATUS.get(status_code, "INTERNAL_ERROR")
    raise EventFlowHTTPException(
        error_code=error_code,
        title=error_code.replace("_", " ").title(),
        status_code=status_code,
        detail=context.error or "Error procesando la reserva",
        instance=instance,
    )


@router.post(
    "/reservar",
    response_model=ReservaResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Reserva ya existente (retry idempotente)", "model": ReservaResponse},
        404: {"description": "Usuario o evento no encontrado", "model": RFC7807Error},
        409: {"description": "Inventario insuficiente / doble venta evitada", "model": RFC7807Error},
        422: {"description": "Datos invalidos (validacion) o categoria inexistente", "model": RFC7807Error},
        500: {"description": "Error interno procesando la SAGA", "model": RFC7807Error},
        503: {"description": "Usuarios Service o Eventos Service no disponible", "model": RFC7807Error},
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
                        "evento_id": "550e8400-e29b-41d4-a716-446655440001",
                        "cantidad": 2,
                        "categoria": "general",
                        "metodo_pago": "tarjeta",
                    }
                }
            }
        }
    },
)
async def crear_reserva(request: Request, response: Response, solicitud: ReservaCreateRequest) -> ReservaResponse:
    """
    Inicia la transaccion SAGA de compra de entradas.

    Chain of Responsibility (6 pasos, 1:1 con la SAGA):
    ValidadorDeDatos -> ValidadorInventario(usuario) -> ValidadorEvento
    -> ProcesadorPago (Redis, atomico) -> ConfirmadorReserva (MongoDB)
    -> Auditor (PostgreSQL event_log).

    Si algun paso falla desde ProcesadorPago en adelante, el
    SagaOrchestrator ejecuta compensaciones automaticas (libera el
    inventario reservado en Redis, revierte el pago) antes de responder.

    reserva_id funciona como idempotency key: reintentar el mismo POST
    con el mismo reserva_id devuelve la reserva ya confirmada (200, no
    se creo nada nuevo) en vez de procesar una segunda compra (201).
    """
    existing = await check_idempotency(solicitud.reserva_id)
    if isinstance(existing, dict) and "_id" in existing:
        response.status_code = status.HTTP_200_OK
        return ReservaResponse(
            reserva_id=str(existing["_id"]),
            estado=existing.get("estado", "confirmada"),
            numero_confirmacion=existing.get("numero_confirmacion", ""),
        )

    context = ReservaContext(
        usuario_id=solicitud.usuario_id,
        evento_id=solicitud.evento_id,
        cantidad=solicitud.cantidad,
        metodo_pago=solicitud.metodo_pago.value,
        categoria=solicitud.categoria,
        reserva_id=solicitud.reserva_id,
    )
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        context.correlation_id = UUID(str(correlation_id))

    orchestrator = SagaOrchestrator(
        chain=ChainBuilder.build(),
        compensation_handlers={
            4: compensate_step_4_payment,
            5: compensate_step_5_reservation,
        },
    )
    context = await orchestrator.execute(context)

    if context.error:
        _raise_from_context(context, "/api/reservar")

    return ReservaResponse(**context.reserva_data)


@router.get("/reservar", response_model=List[ReservaResponse])
async def listar_reservas(
    skip: int = Query(0, ge=0, description="Saltar N registros"),
    limit: int = Query(10, ge=1, le=100, description="Maximo de registros a retornar"),
    usuario_id: Optional[UUID] = Query(None, description="Filtrar por usuario"),
    evento_id: Optional[UUID] = Query(None, description="Filtrar por evento"),
    estado: Optional[str] = Query(None, description="Filtrar por estado de la reserva"),
) -> List[ReservaResponse]:
    """Listar reservas, mas recientes primero (paginado, con filtros opcionales)."""
    collection = await get_reservas_collection()
    filtro = {}
    if usuario_id is not None:
        filtro["usuario_id"] = usuario_id
    if evento_id is not None:
        filtro["evento_id"] = evento_id
    if estado is not None:
        filtro["estado"] = estado
    cursor = collection.find(filtro).sort("creado_en", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [
        ReservaResponse(
            reserva_id=str(doc["_id"]),
            estado=doc.get("estado", ""),
            numero_confirmacion=doc.get("numero_confirmacion", ""),
        )
        for doc in docs
    ]


@router.get(
    "/reservar/{reserva_id}",
    response_model=ReservaResponse,
    responses={404: {"description": "Reserva no encontrada", "model": RFC7807Error}},
)
async def obtener_reserva(reserva_id: UUID) -> ReservaResponse:
    """Obtener una reserva confirmada por ID (para verificar el resultado de una compra)."""
    collection = await get_reservas_collection()
    doc = await collection.find_one({"_id": reserva_id})
    if not doc:
        raise EventFlowHTTPException(
            error_code="RESERVA_NOT_FOUND",
            title="Not Found",
            status_code=404,
            detail="Reserva no encontrada",
            instance=f"/api/reservar/{reserva_id}",
        )
    return ReservaResponse(
        reserva_id=str(doc["_id"]),
        estado=doc.get("estado", ""),
        numero_confirmacion=doc.get("numero_confirmacion", ""),
    )
