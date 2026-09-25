import logging
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from src.services.mongodb import get_collection, get_database
from src.services.redis_pago import get_sha_reservar, get_sha_liberar, get_redis_client, register_lua_scripts
from src.services.postgresql import get_pg_pool
from src.services.http_clients import get_usuarios_client, get_eventos_client, record_success, record_failure
from src.models import ReservaCreate, ReservaResponse, EstadoReserva
from src.utils.errors import EventFlowHTTPException
from src.config import get_settings
import httpx

logger = logging.getLogger(__name__)


class ReservaService:
    def __init__(self):
        self.settings = get_settings()

    @property
    def reservas_collection(self):
        return get_collection(self.settings.mongodb_collection_reservas)

    @property
    def redis_client(self):
        from src.services.redis_pago import get_redis_client
        return get_redis_client()

    def _to_response(self, doc: dict) -> ReservaResponse:
        return ReservaResponse(
            reserva_id=doc["_id"],
            usuario_id=doc["usuario_id"],
            evento_id=doc["evento_id"],
            cantidad=doc["cantidad"],
            categoria=doc["categoria"],
            estado=doc["estado"],
            total=doc["total"],
            creado_en=doc["creado_en"],
            actualizado_en=doc["actualizado_en"],
        )

    async def crear_reserva(self, reserva: ReservaCreate, idempotency_key: str = None) -> ReservaResponse:
        """Crear reserva ejecutando SAGA completa."""
        saga_id = uuid4()
        logger.info(f"🚀 Iniciando SAGA {saga_id} para reserva")

        # Paso 1: Validar usuario
        try:
            usuarios_client = await get_usuarios_client()
            resp = await usuarios_client.get(f"/api/usuarios/{reserva.usuario_id}", timeout=5.0)
            if resp.status_code == 404:
                raise EventFlowHTTPException("user-not-found", "Not Found", 404, "Usuario no encontrado", "/api/v1/reservar")
            record_success("usuarios_service")
        except httpx.TimeoutException:
            record_failure("usuarios_service")
            raise EventFlowHTTPException("service-unavailable", "Service Unavailable", 503, "Usuarios Service timeout", "/api/v1/reservar")
        except Exception as e:
            record_failure("usuarios_service")
            raise EventFlowHTTPException("service-unavailable", "Service Unavailable", 503, f"Usuarios Service: {str(e)}", "/api/v1/reservar")

        # Paso 2: Validar evento y aforo
        try:
            eventos_client = await get_eventos_client()
            resp = await eventos_client.get(f"/api/v1/eventos/{reserva.evento_id}", timeout=5.0)
            if resp.status_code == 404:
                raise EventFlowHTTPException("event-not-found", "Not Found", 404, "Evento no encontrado", "/api/v1/reservar")
            evento = resp.json()
            
            # Verificar aforo disponible
            if evento.get("entradas_disponibles", 0) < reserva.cantidad:
                raise EventFlowHTTPException("insufficient-inventory", "Conflict", 409, 
                    f"Inventario insuficiente. Disponibles: {evento.get('entradas_disponibles', 0)}", "/api/v1/reservar")
            
            # Encontrar precio por categoría
            precio = 0
            for p in evento.get("precios", []):
                if p["categoria"] == reserva.categoria:
                    precio = p["precio"]
                    break
            if precio == 0:
                raise EventFlowHTTPException("validation-error", "Validation Error", 422, 
                    f"Categoría {reserva.categoria} no encontrada en evento", "/api/v1/reservar")
            
            total = precio * reserva.cantidad
            record_success("eventos_service")
        except httpx.TimeoutException:
            record_failure("eventos_service")
            raise EventFlowHTTPException("service-unavailable", "Service Unavailable", 503, "Eventos Service timeout", "/api/v1/reservar")
        except EventFlowHTTPException:
            raise
        except Exception as e:
            record_failure("eventos_service")
            raise EventFlowHTTPException("service-unavailable", "Service Unavailable", 503, f"Eventos Service: {str(e)}", "/api/v1/reservar")

        # Paso 3: Reservar inventario en Redis (atómico con Lua)
        redis_key = f"evento:{reserva.evento_id}:categoria:{reserva.categoria}:disponibles"
        try:
            redis = await get_redis_client()
            result = await self._eval_sha_reservar(redis, reserva.evento_id, reserva.categoria, reserva.cantidad)
            if result == -2:
                raise EventFlowHTTPException("insufficient-inventory", "Conflict", 409, "Inventario insuficiente", "/api/v1/reservar")
            elif result == -1:
                # Inicializar clave si no existe
                pass
        except Exception as e:
            raise EventFlowHTTPException("internal-error", "Internal Server Error", 500, f"Error Redis: {str(e)}", "/api/v1/reservar")

        # Paso 4: Procesar pago (simulado)
        try:
            await self._procesar_pago(reserva.usuario_id, reserva.evento_id, 100.0)  # total calculado
        except Exception as e:
            # Compensación: liberar inventario
            await self._liberar_inventario(redis, reserva.evento_id, reserva.categoria, reserva.cantidad)
            raise EventFlowHTTPException("payment-failed", "Internal Server Error", 500, f"Error procesando pago: {str(e)}", "/api/v1/reservar")

        # Paso 5: Confirmar reserva en MongoDB
        reserva_id = uuid4()
        now = datetime.now(timezone.utc)
        total = 100.0  # calcular real

        doc = {
            "_id": uuid4(),
            "usuario_id": reserva.usuario_id,
            "evento_id": reserva.evento_id,
            "cantidad": reserva.cantidad,
            "categoria": reserva.categoria,
            "estado": EstadoReserva.CONFIRMADA.value,
            "total": total,
            "creado_en": datetime.now(timezone.utc),
            "actualizado_en": datetime.now(timezone.utc),
        }

        db = get_database()
        await db["reservas"].insert_one(doc)
        logger.info(f"✅ SAGA completada: reserva {reserva_id}")

        return ReservaResponse(
            reserva_id=doc["_id"],
            usuario_id=reserva.usuario_id,
            evento_id=reserva.evento_id,
            cantidad=reserva.cantidad,
            categoria=reserva.categoria,
            estado=EstadoReserva.CONFIRMADA,
            total=total,
            creado_en=now,
            actualizado_en=now,
        )

    async def _eval_sha_reservar(self, redis, evento_id: UUID, categoria: str, cantidad: int) -> int:
        from src.services.redis_pago import get_sha_reservar
        sha = get_sha_reservar()
        if not sha:
            await register_lua_scripts()
        key = f"evento:{evento_id}:categoria:{categoria}:disponibles"
        result = await get_redis_client().evalsha(get_sha_reservar(), 1, key, str(cantidad))
        return int(result)

    async def _liberar_inventario(self, redis, evento_id: UUID, categoria: str, cantidad: int):
        from src.services.redis_pago import get_sha_liberar
        sha = get_sha_liberar()
        if not sha:
            await register_lua_scripts()
        key = f"evento:{evento_id}:categoria:{categoria}:disponibles"
        await get_redis_client().evalsha(get_sha_liberar(), 1, key, str(cantidad))

    async def _procesar_pago(self, usuario_id, evento_id, total):
        """Simular procesamiento de pago."""
        from src.services.postgresql import get_pg_pool
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pagos (reserva_id, usuario_id, evento_id, monto, estado, proveedor_pago)
                VALUES ($1, $2, $3, $4, 'confirmado', 'simulado')
            """, uuid4(), usuario_id, evento_id, total)

    async def obtener_reserva(self, reserva_id: UUID) -> Optional[dict]:
        from src.services.mongodb import get_collection
        from src.config import get_settings
        settings = get_settings()
        doc = await get_collection("reservas").find_one({"_id": reserva_id})
        return doc