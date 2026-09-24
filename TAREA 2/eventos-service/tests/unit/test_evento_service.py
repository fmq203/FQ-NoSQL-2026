import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from decimal import Decimal
from src.models.evento import (
    EstadoEvento,
    PrecioCategoria,
    Ubicacion,
    EventoCreate,
    EventoResponse,
)
from src.services.evento_service import EventoService
from src.utils.errors import EventFlowHTTPException


class TestEventoService:
    @pytest.fixture
    def mock_collection(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_collection):
        with patch("src.services.evento_service.get_collection", return_value=mock_collection):
            return EventoService()
    
    @pytest.fixture
    def valid_evento(self):
        return EventoCreate(
            nombre="Test Event",
            estado=EstadoEvento.PUBLICADO,
            aforo_total=1000,
            entradas_disponibles=1000,
            precios=[
                PrecioCategoria(categoria="VIP", precio=Decimal("5000.00"), disponibles=100),
                PrecioCategoria(categoria="General", precio=Decimal("1000.00"), disponibles=900)
            ],
            ubicacion=Ubicacion(ciudad="Buenos Aires", pais="Argentina", direccion="Estadio Test")
        )
    
    @pytest.mark.asyncio
    async def test_create_event_success(self, service, mock_collection, valid_evento):
        mock_collection.insert_one = AsyncMock()
        
        result = await service.create_event(valid_evento)
        
        assert isinstance(result, EventoResponse)
        assert result.nombre == "Test Event"
        assert result.estado == EstadoEvento.PUBLICADO
        assert result.aforo_total == 1000
        assert result.entradas_disponibles == 1000
        assert len(result.precios) == 2
        assert result.evento_id is not None
        assert result.creado_en is not None
        assert result.actualizado_en is not None
        mock_collection.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_event_duplicate_key(self, service, mock_collection, valid_evento):
        from pymongo.errors import DuplicateKeyError
        mock_collection.insert_one = AsyncMock(side_effect=DuplicateKeyError("duplicate key"))
        
        with pytest.raises(EventFlowHTTPException) as exc_info:
            await service.create_event(valid_evento)
        
        assert exc_info.value.error_code == "DUPLICATE_EVENT"
        assert exc_info.value.status_code == 409
    
    @pytest.mark.asyncio
    async def test_create_event_generic_error(self, service, mock_collection, valid_evento):
        mock_collection.insert_one = AsyncMock(side_effect=Exception("DB error"))
        
        with pytest.raises(EventFlowHTTPException) as exc_info:
            await service.create_event(valid_evento)
        
        assert exc_info.value.error_code == "INTERNAL_ERROR"
        assert exc_info.value.status_code == 500
    
    @pytest.mark.asyncio
    async def test_get_event_success(self, service, mock_collection):
        evento_id = str(uuid4())
        mock_document = {
            "_id": UUID(evento_id),
            "nombre": "Test Event",
            "estado": "publicado",
            "aforo_total": 1000,
            "entradas_disponibles": 1000,
            "precios": [
                {"categoria": "VIP", "precio": "5000.00", "disponibles": 100},
                {"categoria": "General", "precio": "1000.00", "disponibles": 900}
            ],
            "ubicacion": {
                "ciudad": "Buenos Aires",
                "pais": "Argentina",
                "direccion": "Estadio Test"
            },
            "creado_en": "2026-09-24T10:00:00.000Z",
            "actualizado_en": "2026-09-24T10:00:00.000Z",
        }
        mock_collection.find_one = AsyncMock(return_value=mock_document)
        
        result = await service.get_event(evento_id)
        
        assert isinstance(result, EventoResponse)
        assert str(result.evento_id) == evento_id
        assert result.nombre == "Test Event"
        assert result.estado == EstadoEvento.PUBLICADO
        assert len(result.precios) == 2
        assert result.precios[0].precio == Decimal("5000.00")
        mock_collection.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_event_not_found(self, service, mock_collection):
        evento_id = str(uuid4())
        mock_collection.find_one = AsyncMock(return_value=None)
        
        with pytest.raises(EventFlowHTTPException) as exc_info:
            await service.get_event(evento_id)
        
        assert exc_info.value.error_code == "NOT_FOUND"
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Evento no encontrado"
    
    @pytest.mark.asyncio
    async def test_get_event_invalid_uuid(self, service, mock_collection):
        with pytest.raises(EventFlowHTTPException) as exc_info:
            await service.get_event("invalid-uuid")
        
        assert exc_info.value.error_code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == "Invalid UUID format"