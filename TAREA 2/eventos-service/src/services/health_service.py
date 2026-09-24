import logging
from datetime import datetime, timezone
from typing import Tuple

from src.services.mongodb import ping_mongodb
from src.models.health import HealthCheckResponse, HealthStatus, MongoDBHealth
from src.config import get_settings

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self):
        self.settings = get_settings()

    async def check_health(self) -> HealthCheckResponse:
        success, latency_ms = await ping_mongodb(self.settings.health_check_timeout_ms)

        if not success:
            status = HealthStatus.UNHEALTHY
            mongodb_status = MongoDBHealth.DOWN
            http_status = 503
        elif latency_ms < self.settings.health_check_degraded_threshold_ms:
            status = HealthStatus.HEALTHY
            mongodb_status = MongoDBHealth.OK
            http_status = 200
        elif latency_ms < self.settings.health_check_unhealthy_threshold_ms:
            status = HealthStatus.DEGRADED
            mongodb_status = MongoDBHealth.SLOW
            http_status = 200
        else:
            status = HealthStatus.UNHEALTHY
            mongodb_status = MongoDBHealth.DOWN
            http_status = 503

        response = HealthCheckResponse(
            status=status,
            checks={"mongodb": mongodb_status},
            timestamp=datetime.now(timezone.utc),
        )

        mongodb_status_str = mongodb_status.value if hasattr(mongodb_status, 'value') else str(mongodb_status)
        
        logger.info(
            f"Health check: {status.value}",
            extra={
                "correlation_id": None,
                "trace_id": None,
                "span_id": None,
                "log_message": f"Health check: {status.value}",
                "context": {
                    "operation": "health_check",
                    "duration_ms": round(latency_ms, 2),
                    "mongodb_status": mongodb_status_str,
                    "mongodb_latency_ms": round(latency_ms, 2),
                },
            },
        )

        return response