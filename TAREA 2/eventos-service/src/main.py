"""
Eventos Service - EventFlow
Gestión de eventos y disponibilidad de entradas.

Ver: brain/microservices/eventos.md
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.services.mongodb import connect_to_mongodb, close_mongodb_connection, mongodb_lifespan
from src.api.middleware.correlation import CorrelationIDMiddleware
from src.api.middleware.logging import StructuredLoggingMiddleware, setup_json_logging
from src.api.routes import eventos, health
from src.utils.errors import (
    EventFlowHTTPException,
    eventflow_exception_handler,
    validation_exception_handler,
    pydantic_validation_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError


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
        title="Eventos Service",
        version="1.0.0",
        description="CRUD de eventos con health check - EventFlow Platform",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)

    app.add_exception_handler(EventFlowHTTPException, eventflow_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    app.include_router(eventos.router, prefix="/api")
    app.include_router(health.router, prefix="")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)