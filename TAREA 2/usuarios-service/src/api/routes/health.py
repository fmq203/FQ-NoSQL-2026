from fastapi import APIRouter, Depends, Response
from src.services.health_service import HealthService
from src.models.health import HealthCheckResponse, HealthStatus

router = APIRouter(tags=["health"])


def get_health_service() -> HealthService:
    return HealthService()


@router.get("/health", response_model=HealthCheckResponse, summary="Health check")
async def health_check(
    response: Response,
    service: HealthService = Depends(get_health_service),
):
    """Health check del servicio de usuarios."""
    result = await service.check_health()
    if result.status == HealthStatus.UNHEALTHY:
        response.status_code = 503
    return result