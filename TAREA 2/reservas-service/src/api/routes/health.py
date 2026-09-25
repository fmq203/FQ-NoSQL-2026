from fastapi import APIRouter, Depends, Response, Request
from src.services.health_service import HealthService
from src.models import HealthCheckResponse

router = APIRouter(tags=["health"])


def get_health_service() -> HealthService:
    return HealthService()


@router.get("/health", summary="Health check")
async def health_check(
    request: Request,
    response: Response,
    service: HealthService = Depends(get_health_service),
):
    """Health check con estado de todas las dependencias."""
    result = await service.check_health(request)
    if result["status"] == "unhealthy":
        response.status_code = 503
    return result