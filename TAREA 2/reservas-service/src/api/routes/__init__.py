"""API routes for Reservas Service."""
from fastapi import APIRouter
from .reservas import router as reservas_router
from .health import router as health_router
from .metrics import router as metrics_router

router = APIRouter()
router.include_router(reservas_router, prefix="/api")
router.include_router(health_router, prefix="")
router.include_router(metrics_router, prefix="")

__all__ = ["router"]
