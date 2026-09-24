from fastapi import APIRouter, Depends, status
from src.models.evento import EventoCreate, EventoResponse
from src.services.evento_service import EventoService
from src.utils.errors import EventFlowHTTPException
from uuid import UUID

router = APIRouter(prefix="/v1/eventos", tags=["eventos"])


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