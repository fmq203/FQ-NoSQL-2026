import logging
import time
from datetime import datetime, timezone
from src.services.mongodb import ping_mongodb, get_mongo_client
from src.services.redis_pago import get_redis_client
from src.services.postgresql import get_pg_pool
from src.services.http_clients import get_usuarios_client, get_eventos_client, get_circuit_breaker_state
from src.models import HealthCheckResponse
from src.config import get_settings

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self):
        self.settings = get_settings()

    async def check_health(self, request=None) -> dict:
        checks = {}
        overall_status = "healthy"

        # MongoDB
        try:
            start = time.perf_counter()
            client = get_mongo_client()
            await client.admin.command("ping")
            latency_ms = (time.perf_counter() - start) * 1000
            if latency_ms > 100:
                checks["mongodb"] = "degraded"
                overall_status = "degraded" if overall_status == "healthy" else overall_status
            else:
                checks["mongodb"] = "ok"
        except Exception as e:
            logger.warning(f"MongoDB health check falló: {e}")
            checks["mongodb"] = "down"
            overall_status = "unhealthy"

        # Redis
        try:
            start = time.perf_counter()
            client = await get_redis_client()
            await client.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            if latency_ms > 50:
                checks["redis"] = "degraded"
                overall_status = "degraded" if overall_status == "healthy" else overall_status
            else:
                checks["redis"] = "ok"
        except Exception as e:
            logger.warning(f"Redis health check falló: {e}")
            checks["redis"] = "down"
            overall_status = "unhealthy"

        # PostgreSQL
        try:
            start = time.perf_counter()
            pool = await get_pg_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency_ms = (time.perf_counter() - start) * 1000
            if latency_ms > 100:
                checks["postgresql"] = "degraded"
                overall_status = "degraded" if overall_status == "healthy" else overall_status
            else:
                checks["postgresql"] = "ok"
        except Exception as e:
            logger.warning(f"PostgreSQL health check falló: {e}")
            checks["postgresql"] = "down"
            overall_status = "unhealthy"

        # Circuit breakers
        cb_states = get_circuit_breaker_state()
        for service, state in cb_states.items():
            if state == "open":
                checks[service] = "down"
                overall_status = "unhealthy"
            elif state == "half-open":
                checks[service] = "degraded"
                overall_status = "degraded" if overall_status == "healthy" else overall_status
            else:
                checks[service] = "ok"

        # External services (HTTP clients) - active checks
        for service_name, client_factory in [
            ("usuarios_service", get_usuarios_client),
            ("eventos_service", get_eventos_client)
        ]:
            try:
                start = time.perf_counter()
                client = await client_factory()
                response = await client.get("/health", timeout=2.0)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    if latency_ms > 2000:
                        checks[service_name] = "degraded"
                        overall_status = "degraded" if overall_status == "healthy" else overall_status
                    else:
                        checks[service_name] = "ok"
                else:
                    checks[service_name] = "degraded"
                    overall_status = "degraded" if overall_status == "healthy" else overall_status
            except Exception as e:
                logger.warning(f"Health check {service_name} falló: {e}")
                checks[service_name] = "down"
                overall_status = "unhealthy"

        return {
            "status": overall_status,
            "checks": checks,
            "service": "reservas-service",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }