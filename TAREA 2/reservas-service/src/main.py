"""
Reservas & Pagos Service - EventFlow
Orquestador SAGA con Chain of Responsibility para reservas y pagos.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.services.mongodb import connect_to_mongodb, close_mongodb_connection
from src.services.redis_pago import register_lua_scripts, close_redis_connection
from src.services.postgresql import init_pg_schema, close_pg_pool
from src.services.http_clients import close_http_clients
from src.api.middleware.correlation import CorrelationIDMiddleware
from src.api.middleware.logging import StructuredLoggingMiddleware, setup_json_logging
from src.api.middleware.metrics import MetricsMiddleware
from src.api.routes import router
from src.utils.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_json_logging(settings.log_level)
    await connect_to_mongodb()
    await register_lua_scripts()
    await init_pg_schema()
    yield
    await close_mongodb_connection()
    await close_redis_connection()
    await close_pg_pool()
    await close_http_clients()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Reservas & Pagos Service",
        version="1.0.0",
        description="Orquestador SAGA con Chain of Responsibility para reservas y pagos",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(MetricsMiddleware)

    register_exception_handlers(app)

    app.include_router(router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)