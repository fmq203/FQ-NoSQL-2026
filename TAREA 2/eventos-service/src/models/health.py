from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class MongoDBHealth(str, Enum):
    OK = "ok"
    SLOW = "slow"
    DOWN = "down"


class HealthCheckResponse(BaseModel):
    status: HealthStatus
    checks: dict = Field(default_factory=dict)
    timestamp: datetime

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "examples": [
                {
                    "status": "healthy",
                    "checks": {"mongodb": "ok"},
                    "timestamp": "2026-09-23T10:00:00.000Z"
                },
                {
                    "status": "degraded",
                    "checks": {"mongodb": "slow"},
                    "timestamp": "2026-09-23T10:00:00.000Z"
                },
                {
                    "status": "unhealthy",
                    "checks": {"mongodb": "down"},
                    "timestamp": "2026-09-23T10:00:00.000Z"
                }
            ]
        }