from .eventos import router as eventos_router
from .health import router as health_router
from .metrics import router as metrics_router

__all__ = ["eventos_router", "health_router", "metrics_router"]