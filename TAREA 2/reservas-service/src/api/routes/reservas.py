"""Endpoint POST /api/reservar - inicia la SAGA completa de compra de entradas."""
import logging
from uuid import UUID

from fastapi import APIRouter, Request, status

from src.chain.builder import ChainBuilder
from src.models.reserva import ReservaContext, ReservaCreateRequest, ReservaResponse
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
    400: "validation-error",
    404: "not-found",
    409: "conflict",
    422: "validation-error",
    500: "internal-error",
    503: "service-unavailable",
}


def _raise_from_context(context: ReservaContext, instance: str) -> None:
    status_code = context.status_code or 500
    error_code = _ERROR_CODE_BY_STATUS.get(status_code, "internal-error")
    raise EventFlowHTTPException(
        error_code=error_code,
        title=error_code.replace("-", " ").title(),
        status_code=status_code,
        detail=context.error or "Error procesando la reserva",
        instance=instance,
    )


@router.post("/reservar", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
async def crear_reserva(request: Request, solicitud: ReservaCreateRequest) -> ReservaResponse:
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
    con el mismo reserva_id devuelve la reserva ya confirmada en vez de
    procesar una segunda compra.
    """
    existing = await check_idempotency(solicitud.reserva_id)
    if isinstance(existing, dict) and "_id" in existing:
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


@router.get("/reservar/{reserva_id}", response_model=ReservaResponse)
async def obtener_reserva(reserva_id: UUID) -> ReservaResponse:
    """Obtener una reserva confirmada por ID (para verificar el resultado de una compra)."""
    collection = await get_reservas_collection()
    doc = await collection.find_one({"_id": reserva_id})
    if not doc:
        raise EventFlowHTTPException(
            error_code="not-found",
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
