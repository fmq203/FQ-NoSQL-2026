import logging
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.services.mongodb import get_collection
from src.models.evento import EventoCreate, EventoResponse, EventoInDB, AjusteInventarioResponse
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
                    instance="/api/eventos",
                )
            logger.error(f"Failed to create event: {e}")
            raise EventFlowHTTPException(
                error_code="INTERNAL_ERROR",
                detail="Failed to create event",
                status_code=500,
                instance="/api/eventos",
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
                instance=f"/api/eventos/{evento_id}",
            )

        document = await self.collection.find_one({"_id": bson_uuid})

        if not document:
            raise EventFlowHTTPException(
                error_code="NOT_FOUND",
                detail="Evento no encontrado",
                status_code=404,
                instance=f"/api/eventos/{evento_id}",
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

    async def _ajustar_inventario(
        self, evento_id: str, categoria: str, cantidad: int, signo: int
    ) -> AjusteInventarioResponse:
        """Ajusta atomicamente precios[].disponibles y entradas_disponibles
        para una categoria. signo=-1 decrementa (venta), signo=+1 incrementa
        (compensacion). El decremento usa un filtro $elemMatch que exige
        disponibles >= cantidad, asi que nunca puede quedar en negativo
        aunque dos llamadas lleguen casi al mismo tiempo (aunque en la
        practica Redis ya es quien arbitra la concurrencia real - esto es
        una defensa adicional, no la fuente de verdad de "no hay doble
        venta").
        """
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
                instance=f"/api/eventos/{evento_id}",
            )

        delta = signo * cantidad
        query: dict = {"_id": bson_uuid, "precios.categoria": categoria}
        if signo < 0:
            query["precios"] = {"$elemMatch": {"categoria": categoria, "disponibles": {"$gte": cantidad}}}

        result = await self.collection.find_one_and_update(
            query,
            {
                "$inc": {
                    "precios.$[elem].disponibles": delta,
                    "entradas_disponibles": delta,
                },
                "$set": {"actualizado_en": datetime.now(timezone.utc)},
            },
            array_filters=[{"elem.categoria": categoria}],
            return_document=True,
        )

        if not result:
            existe = await self.collection.find_one({"_id": bson_uuid})
            if not existe:
                raise EventFlowHTTPException(
                    error_code="NOT_FOUND",
                    detail="Evento no encontrado",
                    status_code=404,
                    instance=f"/api/eventos/{evento_id}",
                )
            categoria_existe = any(p["categoria"] == categoria for p in existe.get("precios", []))
            if not categoria_existe:
                raise EventFlowHTTPException(
                    error_code="VALIDATION_ERROR",
                    detail=f"Categoria '{categoria}' no existe en este evento",
                    status_code=422,
                    instance=f"/api/eventos/{evento_id}",
                )
            # La categoria existe: si llegamos aca con signo<0 fue por stock
            # insuficiente (el $elemMatch con disponibles >= cantidad no matcheo).
            raise EventFlowHTTPException(
                error_code="INSUFFICIENT_INVENTORY",
                detail=f"Inventario insuficiente en categoria '{categoria}'",
                status_code=409,
                instance=f"/api/eventos/{evento_id}",
            )

        precio_actualizado = next(
            (p for p in result.get("precios", []) if p["categoria"] == categoria), None
        )
        return AjusteInventarioResponse(
            evento_id=result["_id"],
            categoria=categoria,
            disponibles=precio_actualizado["disponibles"] if precio_actualizado else 0,
            entradas_disponibles=result["entradas_disponibles"],
        )

    async def decrementar_inventario(self, evento_id: str, categoria: str, cantidad: int) -> AjusteInventarioResponse:
        """Registrar una venta confirmada (llamado por reservas-service tras el pago)."""
        return await self._ajustar_inventario(evento_id, categoria, cantidad, signo=-1)

    async def incrementar_inventario(self, evento_id: str, categoria: str, cantidad: int) -> AjusteInventarioResponse:
        """Compensacion: revertir una venta que no se pudo confirmar."""
        return await self._ajustar_inventario(evento_id, categoria, cantidad, signo=1)