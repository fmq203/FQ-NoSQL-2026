from fastapi import APIRouter, Depends
from src.services.health_service import HealthService

router = APIRouter(tags=["health"])


def get_health_service() -> HealthService:
    return HealthService()


@router.get("/health", summary="Health check")
async def health_check(service: HealthService = Depends(get_health_service)):
    return await service.check_health()