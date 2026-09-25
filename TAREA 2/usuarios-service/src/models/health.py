from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Dict


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class MongoDBHealth(str, Enum):
    OK = "ok"
    SLOW = "slow"
    DOWN = "down"


class RedisHealth(str, Enum):
    OK = "ok"
    SLOW = "slow"
    DOWN = "down"


class PostgreSQLHealth(str, Enum):
    OK = "ok"
    SLOW = "slow"
    DOWN = "down"


class HealthCheckResponse(BaseModel):
    status: HealthStatus
    checks: Dict[str, str]
    timestamp: datetime