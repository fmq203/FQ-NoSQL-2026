"""API routes for Reservas Service."""
from fastapi import APIRouter
from .reservas import router as reservas_router
from .health import router as health_router

router = APIRouter()
router.include_router(reservas_router, prefix="/api/v1")
router.include_router(health_router, prefix="")

__all__ = ["router"]