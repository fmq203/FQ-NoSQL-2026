"""API routes for Reservas Service."""
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from uuid import UUID, uuid4
from typing import Optional
import logging

from src.models.reserva import ReservaRequest, ReservaResponse, ReservaContext
from src.chain.validators import ChainBuilder
from src.services.mongo import get_reservas_collection
from src.utils.idempotency import check_idempotency, generate_confirmation_number
from src.api.middleware import (
    ValidationError, NotFoundError, ConflictError, 
    ServiceUnavailableError, InternalError,
    UserNotFoundError, EventNotFoundError, InsufficientInventoryError,
    IdempotencyConflictError, PaymentFailedError, ReservationFailedError
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ReservaCreateRequest(BaseModel):
    """Request body for creating reservation."""
    usuario_id: UUID
    evento_id: UUID
    cantidad: int
    metodo_pago: str


@router.post("/reservar", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
async def crear_reserva(request: ReservaCreateRequest, http_request: Request):
    """
    Inicia SAGA completa para crear una reserva.
    
    Flujo: ValidarDatos → Usuario → Evento → PagoRedis → ReservaMongo → AuditPG
    """
    correlation_id = getattr(http_request.state, "correlation_id", str(uuid4()))
    
    # Build context
    context = ReservaContext(
        usuario_id=request.usuario_id,
        evento_id=request.evento_id,
        cantidad=request.cantidad,
        metodo_pago=request.metodo_pago,
        reserva_id=uuid4(),
        correlation_id=UUID(correlation_id),
    )
    
    # Check idempotency
    existing = await check_idempotency(context.reserva_id)
    if existing:
        raise IdempotencyConflictError()
    
    # Build and execute chain
    chain = ChainBuilder.build()
    context = await chain.handle(context)
    
    # Check result
    if context.error:
        logger.error(f"SAGA failed: {context.error}", extra={
            "correlation_id": correlation_id,
            "reserva_id": str(context.reserva_id),
            "status_code": context.status_code,
        })
        
        # Map status codes to appropriate exceptions
        if context.status_code == 404:
            if "Usuario" in context.error:
                raise UserNotFoundError()
            elif "Evento" in context.error:
                raise EventNotFoundError()
            else:
                raise NotFoundError(context.error)
        elif context.status_code == 409:
            if "INSUFICIENTE" in context.error or "aforo" in context.error.lower():
                # Extract available count if possible
                raise InsufficientInventoryError(0)
            elif "idempotent" in context.error.lower() or "existente" in context.error.lower():
                raise IdempotencyConflictError()
            else:
                raise ConflictError(context.error)
        elif context.status_code == 422:
            raise ValidationError(context.error)
        elif context.status_code == 503:
            raise ServiceUnavailableError(context.error)
        elif context.status_code == 500:
            if "pago" in context.error.lower() or "lua" in context.error.lower():
                raise PaymentFailedError(context.error)
            else:
                raise InternalError(context.error)
        else:
            raise InternalError(context.error)
    
    # Success
    logger.info(f"SAGA completed successfully", extra={
        "correlation_id": correlation_id,
        "reserva_id": str(context.reserva_id),
        "numero_confirmacion": context.reserva_data.get("numero_confirmacion"),
    })
    
    return ReservaResponse(
        reserva_id=str(context.reserva_id),
        estado=context.reserva_data.get("estado", "confirmada"),
        numero_confirmacion=context.reserva_data.get("numero_confirmacion", ""),
    )


@router.get("/reservar/{reserva_id}", response_model=ReservaResponse)
async def obtener_reserva(reserva_id: UUID, request: Request):
    """Obtiene una reserva por ID."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    
    collection = await get_reservas_collection()
    reserva = await collection.find_one({"_id": reserva_id})
    
    if not reserva:
        raise NotFoundError("Reserva no encontrada", "NOT_FOUND")
    
    return ReservaResponse(
        reserva_id=str(reserva["_id"]),
        estado=reserva.get("estado", ""),
        numero_confirmacion=reserva.get("numero_confirmacion", ""),
    )


@router.get("/reservar")
async def listar_reservas(
    request: Request,
    usuario_id: Optional[UUID] = None,
    evento_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
):
    """Lista reservas con filtros opcionales."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    
    collection = await get_reservas_collection()
    
    query = {}
    if usuario_id:
        query["usuario_id"] = usuario_id
    if evento_id:
        query["evento_id"] = evento_id
    if estado:
        query["estado"] = estado
    
    cursor = collection.find(query).sort("creado_en", -1).skip(skip).limit(limit)
    reservas = await cursor.to_list(length=limit)
    
    return [
        ReservaResponse(
            reserva_id=str(r["_id"]),
            estado=r.get("estado", ""),
            numero_confirmacion=r.get("numero_confirmacion", ""),
        )
        for r in reservas
    ]