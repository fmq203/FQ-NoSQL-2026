from fastapi import APIRouter, Depends, HTTPException, status, Request
from src.models import ReservaCreate, ReservaResponse, EstadoReserva
from src.services.reserva_service import ReservaService
from src.utils.errors import EventFlowHTTPException
from uuid import UUID
from typing import Optional

router = APIRouter(prefix="/reservar", tags=["reservas"])


def get_reserva_service() -> ReservaService:
    return ReservaService()


@router.post("/reservar", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
async def crear_reserva(
    request: Request,
    reserva: ReservaCreate,
    service: ReservaService = Depends(get_reserva_service),
):
    """
    Iniciar transacción SAGA para reserva y pago.

    Valida:
    - Usuario existe (Usuarios Service)
    - Evento existe y tiene aforo (Eventos Service)
    - Inventario disponible en Redis (atómico)
    - Procesar pago
    - Confirmar reserva en MongoDB

    Compensaciones automáticas en caso de fallo.
    """
    try:
        # Obtener idempotency key del header
        idempotency_key = request.headers.get("Idempotency-Key")
        return await service.crear_reserva(reserva, idempotency_key)
    except EventFlowHTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar reserva"
        )


@router.get("/reservar/{reserva_id}", response_model=ReservaResponse)
async def obtener_reserva(
    reserva_id: UUID,
    service: ReservaService = Depends(get_reserva_service),
):
    """Obtener reserva por ID."""
    reserva = await service.obtener_reserva(reserva_id)
    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada"
        )
    return reserva