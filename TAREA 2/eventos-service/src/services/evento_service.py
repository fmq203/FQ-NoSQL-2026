import logging
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.services.mongodb import get_collection
from src.models.evento import EventoCreate, EventoResponse, EventoInDB
from src.utils.errors import EventFlowHTTPException

logger = logging.getLogger(__name__)


class EventoService:
    def __init__(self):
        self.collection = get_collection()
    
    async def create_event(self, evento: EventoCreate) -> EventoResponse:
        evento_id = uuid4()
        now = datetime.now(timezone.utc)
        
        document = {
            "_id": evento_id,
            "nombre": evento.nombre,
            "estado": evento.estado.value,
            "aforo_total": evento.aforo_total,
            "entradas_disponibles": evento.entradas_disponibles,
            "precios": [
                {
                    "categoria": p.categoria,
                    "precio": str(p.precio),
                    "disponibles": p.disponibles
                }
                for p in evento.precios
            ],
            "ubicacion": {
                "ciudad": evento.ubicacion.ciudad,
                "pais": evento.ubicacion.pais,
                "direccion": evento.ubicacion.direccion
            },
            "creado_en": now,
            "actualizado_en": now,
        }
        
        try:
            await self.collection.insert_one(document)
            
            logger.info(
                "Event created successfully",
                extra={
                    "correlation_id": None,
                    "trace_id": None,
                    "span_id": None,
                    "log_message": "Event created successfully",
                    "context": {
                        "evento_id": str(evento_id),
                        "operation": "create_event",
                        "duration_ms": 0,
                    },
                },
            )
            
            return EventoResponse(
                evento_id=evento_id,
                nombre=evento.nombre,
                estado=evento.estado,
                aforo_total=evento.aforo_total,
                entradas_disponibles=evento.entradas_disponibles,
                precios=evento.precios,
                ubicacion=evento.ubicacion,
                creado_en=now,
                actualizado_en=now,
            )
        except Exception as e:
            if "duplicate key" in str(e).lower():
                raise EventFlowHTTPException(
                    error_code="DUPLICATE_EVENT",
                    detail="Evento already exists",
                    status_code=409,
                    instance="/api/v1/eventos",
                )
            logger.error(f"Failed to create event: {e}")
            raise EventFlowHTTPException(
                error_code="INTERNAL_ERROR",
                detail="Failed to create event",
                status_code=500,
                instance="/api/v1/eventos",
            )
    
    async def get_event(self, evento_id: str) -> EventoResponse:
        from bson import Binary
        from bson.errors import InvalidId
        import uuid as uuid_module
        
        try:
            parsed_uuid = uuid_module.UUID(evento_id)
            bson_uuid = Binary.from_uuid(parsed_uuid)
        except (ValueError, InvalidId):
            raise EventFlowHTTPException(
                error_code="VALIDATION_ERROR",
                detail="Invalid UUID format",
                status_code=422,
                instance=f"/api/v1/eventos/{evento_id}",
            )
        
        document = await self.collection.find_one({"_id": bson_uuid})
        
        if not document:
            raise EventFlowHTTPException(
                error_code="NOT_FOUND",
                detail="Evento no encontrado",
                status_code=404,
                instance=f"/api/v1/eventos/{evento_id}",
            )
        
        precios = [
            {"categoria": p["categoria"], "precio": Decimal(p["precio"]), "disponibles": p["disponibles"]}
            for p in document.get("precios", [])
        ]
        
        return EventoResponse(
            evento_id=document["_id"],
            nombre=document["nombre"],
            estado=document["estado"],
            aforo_total=document["aforo_total"],
            entradas_disponibles=document["entradas_disponibles"],
            precios=precios,
            ubicacion=document["ubicacion"],
            creado_en=document["creado_en"],
            actualizado_en=document["actualizado_en"],
        )