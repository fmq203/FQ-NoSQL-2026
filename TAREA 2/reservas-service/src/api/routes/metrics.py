from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from src.services.metrics import get_registry

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    summary="Prometheus metrics exposition",
    description="Exposes SAGA step latency, compensation counts, DB/HTTP "
    "operation latency and circuit breaker state (Constitution Principle IV).",
    response_class=Response,
)
async def get_metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(get_registry()), media_type=CONTENT_TYPE_LATEST)
