"""API routes for Reservas Service."""
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from uuid import UUID, uuid4
from typing import Optional
import logging
import time

from ..models.reserva import ReservaCreateRequest, ReservaResponse, ReservaContext
from ..chain.validators import ChainBuilder
from ..services.mongo import get_reservas_collection
from ..utils.idempotency import check_idempotency, generate_confirmation_number
from ..services.metrics import record_http_request_duration
from ..api.middleware import (
    ValidationError, NotFoundError, ConflictError,
    ServiceUnavailableError, InternalError,
    UserNotFoundError, EventNotFoundError, InsufficientInventoryError,
    IdempotencyConflictError, PaymentFailedError, ReservationFailedError
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/reservar",
    response_model=ReservaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear reserva de entradas",
    description="Inicia SAGA completa para crear una reserva: ValidarDatos → Usuario → Evento → PagoRedis → ReservaMongo → AuditPG",
    responses={
        201: {
            "description": "Reserva creada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "reserva_id": "550e8400-e29b-41d4-a716-446655440000",
                        "estado": "confirmada",
                        "numero_confirmacion": "CONF-20260920-A1B2C3D4"
                    }
                }
            }
        },
        200: {
            "description": "Reserva idempotente (ya existía)",
            "content": {
                "application/json": {
                    "example": {
                        "reserva_id": "550e8400-e29b-41d4-a716-446655440000",
                        "estado": "confirmada",
                        "numero_confirmacion": "CONF-20260920-A1B2C3D4"
                    }
                }
            }
        },
        400: {"model": dict, "description": "Error de validación (VALIDATION_ERROR)"},
        404: {"model": dict, "description": "Usuario o evento no encontrado (USER_NOT_FOUND, EVENT_NOT_FOUND)"},
        409: {"model": dict, "description": "Inventario insuficiente o conflicto de idempotencia (INSUFFICIENT_INVENTORY, IDEMPOTENCY_CONFLICT)"},
        500: {"model": dict, "description": "Error interno (PAYMENT_FAILED, RESERVATION_FAILED, INTERNAL_ERROR)"},
        503: {"model": dict, "description": "Servicio no disponible (SERVICE_UNAVAILABLE)"},
    },
)
async def crear_reserva(request: ReservaCreateRequest, http_request: Request):
    """
    Inicia SAGA completa para crear una reserva.

    Flujo: ValidarDatos → Usuario → Evento → PagoRedis → ReservaMongo → AuditPG

    **Ejemplo de request:**
    ```json
    {
        "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
        "evento_id": "550e8400-e29b-41d4-a716-446655440001",
        "cantidad": 2,
        "metodo_pago": "tarjeta"
    }
    ```
    """
    start_time = time.perf_counter()
    correlation_id = getattr(http_request.state, "correlation_id", str(uuid4()))

    # Use provided reserva_id for idempotency, or generate new one
    reserva_id = request.reserva_id or uuid4()

    # Build context
    context = ReservaContext(
        usuario_id=request.usuario_id,
        evento_id=request.evento_id,
        cantidad=request.cantidad,
        metodo_pago=request.metodo_pago,
        reserva_id=reserva_id,
        correlation_id=UUID(correlation_id),
    )

    # Check idempotency
    existing = await check_idempotency(reserva_id)
    if existing:
        logger.info(f"Idempotent request detected for reserva_id: {reserva_id}")
        # Return existing reservation data with 200 OK (idempotent)
        collection = await get_reservas_collection()
        existing_doc = await collection.find_one({"_id": reserva_id})
        if existing_doc:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=ReservaResponse(
                    reserva_id=str(existing_doc["_id"]),
                    estado=existing_doc.get("estado", "confirmada"),
                    numero_confirmacion=existing_doc.get("numero_confirmacion", "")
                ).model_dump()
            )
        # If not found in DB but idempotency key exists, treat as conflict
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

    duration = time.perf_counter() - start_time
    record_http_request_duration("POST", "/api/v1/reservar", 201, duration)

    return ReservaResponse(
        reserva_id=str(context.reserva_id),
        estado=context.reserva_data.get("estado", "confirmada"),
        numero_confirmacion=context.reserva_data.get("numero_confirmacion", ""),
    )


@router.get(
    "/reservar/{reserva_id}",
    response_model=ReservaResponse,
    summary="Obtener reserva por ID",
    description="Obtiene los detalles de una reserva existente",
    responses={
        200: {
            "description": "Reserva encontrada",
            "content": {
                "application/json": {
                    "example": {
                        "reserva_id": "550e8400-e29b-41d4-a716-446655440000",
                        "estado": "confirmada",
                        "numero_confirmacion": "CONF-20260920-A1B2C3D4"
                    }
                }
            }
        },
        404: {"model": dict, "description": "Reserva no encontrada (NOT_FOUND)"},
    },
)
async def obtener_reserva(reserva_id: UUID, request: Request):
    """Obtiene una reserva por ID."""
    start_time = time.perf_counter()
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

    collection = await get_reservas_collection()
    reserva = await collection.find_one({"_id": reserva_id})

    if not reserva:
        duration = time.perf_counter() - start_time
        record_http_request_duration("GET", "/api/v1/reservar/{reserva_id}", 404, duration)
        raise NotFoundError("Reserva no encontrada", "NOT_FOUND")

    duration = time.perf_counter() - start_time
    record_http_request_duration("GET", "/api/v1/reservar/{reserva_id}", 200, duration)

    return ReservaResponse(
        reserva_id=str(reserva["_id"]),
        estado=reserva.get("estado", ""),
        numero_confirmacion=reserva.get("numero_confirmacion", ""),
    )


@router.get(
    "/reservar",
    response_model=list[ReservaResponse],
    summary="Listar reservas",
    description="Lista reservas con filtros opcionales por usuario, evento y estado",
    responses={
        200: {
            "description": "Lista de reservas",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "reserva_id": "550e8400-e29b-41d4-a716-446655440000",
                            "estado": "confirmada",
                            "numero_confirmacion": "CONF-20260920-A1B2C3D4"
                        },
                        {
                            "reserva_id": "550e8400-e29b-41d4-a716-446655440001",
                            "estado": "confirmada",
                            "numero_confirmacion": "CONF-20260920-B2C3D4E5"
                        }
                    ]
                }
            }
        },
    },
)
async def listar_reservas(
    request: Request,
    usuario_id: Optional[UUID] = None,
    evento_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
):
    """Lista reservas con filtros opcionales."""
    start_time = time.perf_counter()
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

    duration = time.perf_counter() - start_time
    record_http_request_duration("GET", "/api/v1/reservar", 200, duration)

    return [
        ReservaResponse(
            reserva_id=str(r["_id"]),
            estado=r.get("estado", ""),
            numero_confirmacion=r.get("numero_confirmacion", ""),
        )
        for r in reservas
    ]