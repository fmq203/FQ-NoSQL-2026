from fastapi import APIRouter, Depends, status
from src.models.evento import EventoCreate, EventoResponse, AjusteInventarioRequest, AjusteInventarioResponse
from src.services.evento_service import EventoService
from src.utils.errors import EventFlowHTTPException
from uuid import UUID

router = APIRouter(prefix="/eventos", tags=["eventos"])


def get_evento_service() -> EventoService:
    return EventoService()


@router.post("", response_model=EventoResponse, status_code=status.HTTP_201_CREATED, summary="Crear evento")
async def crear_evento(
    evento: EventoCreate,
    service: EventoService = Depends(get_evento_service),
):
    return await service.create_event(evento)


@router.get("/{evento_id}", response_model=EventoResponse, summary="Obtener evento por ID")
async def obtener_evento(
    evento_id: UUID,
    service: EventoService = Depends(get_evento_service),
):
    return await service.get_event(str(evento_id))


@router.post(
    "/{evento_id}/decrementar-inventario",
    response_model=AjusteInventarioResponse,
    summary="Registrar una venta confirmada (uso interno, llamado por reservas-service)",
)
async def decrementar_inventario(
    evento_id: UUID,
    ajuste: AjusteInventarioRequest,
    service: EventoService = Depends(get_evento_service),
):
    """
    Decrementa atomicamente precios[].disponibles y entradas_disponibles
    para la categoria indicada. 409 si no hay suficiente inventario, 422 si
    la categoria no existe en el evento.

    Redis (en reservas-service) ya es quien arbitra la concurrencia real
    para evitar dobles ventas; este endpoint solo sincroniza el resultado
    hacia el documento del evento para que GET /api/eventos/{id} refleje
    ventas reales en vez del aforo de creacion.
    """
    return await service.decrementar_inventario(str(evento_id), ajuste.categoria, ajuste.cantidad)


@router.post(
    "/{evento_id}/incrementar-inventario",
    response_model=AjusteInventarioResponse,
    summary="Compensacion SAGA: revertir una venta que no se pudo confirmar (uso interno)",
)
async def incrementar_inventario(
    evento_id: UUID,
    ajuste: AjusteInventarioRequest,
    service: EventoService = Depends(get_evento_service),
):
    """Llamado por reservas-service cuando una SAGA falla despues de haber
    decrementado el inventario, para devolverlo."""
    return await service.incrementar_inventario(str(evento_id), ajuste.categoria, ajuste.cantidad)