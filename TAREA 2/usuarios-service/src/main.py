"""
Usuarios Service - EventFlow
Gestión de usuarios y perfiles.

Ver: brain/microservices/usuarios.md
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.services.mongodb import connect_to_mongodb, close_mongodb_connection
from src.api.middleware.correlation import CorrelationIDMiddleware
from src.api.middleware.logging import StructuredLoggingMiddleware, setup_json_logging
from src.api.middleware.metrics import MetricsMiddleware
from src.api.routes import usuarios, health, metrics
from src.utils.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_json_logging(settings.log_level)
    await connect_to_mongodb()
    yield
    await close_mongodb_connection()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Usuarios Service",
        version="1.0.0",
        description="Gestión de usuarios y perfiles - EventFlow Platform",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Orden importa: Starlette hace wrap del ultimo add_middleware() hacia
    # afuera, asi que el ULTIMO agregado es el que corre PRIMERO en el
    # pre-procesamiento de la request. StructuredLoggingMiddleware lee
    # request.state.correlation_id (con un fallback a un uuid4() propio si
    # no existe todavia), asi que CorrelationIDMiddleware -que lo setea-
    # debe agregarse DESPUES para quedar mas afuera y correr antes.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(MetricsMiddleware)

    register_exception_handlers(app)

    app.include_router(usuarios.router, prefix="")
    app.include_router(health.router, prefix="")
    app.include_router(metrics.router, prefix="")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)