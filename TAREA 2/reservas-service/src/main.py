"""Main FastAPI application for Reservas Service."""
import os
import logging
from contextlib import asynccontextmanager
from uuid import uuid4
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import services
from src.services.mongo import init_mongodb_indexes, close_mongodb_connection
from src.services.redis_pago import register_lua_scripts, close_redis_connection
from src.services.postgresql import init_pg_schema, close_pg_pool
from src.services.http_clients import close_http_clients, get_circuit_breaker_state
from src.services.logging_config import setup_logging
from src.api.middleware import RFC7807Middleware
from src.api.versioning import APIVersioningMiddleware
from src.api.tracing import TracingMiddleware
from src.api.circuit_breaker import get_all_circuit_states
from src.api.routes import router

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


# RFC 7807 Error Response Models for OpenAPI documentation
class RFC7807Error(BaseModel):
    """RFC 7807 Problem Details error response."""
    type: str = Field(..., description="URI identifying the error type", example="https://eventflow.example.com/errors/validation_error")
    title: str = Field(..., description="Short, human-readable summary of the error", example="Validation Error")
    status: int = Field(..., description="HTTP status code", example=400)
    detail: str = Field(..., description="Human-readable explanation of the error", example="UUID inválido")
    instance: str = Field(..., description="URI reference identifying the specific occurrence", example="/api/v1/reservar")
    correlation_id: str = Field(..., description="Correlation ID for tracing", example="550e8400-e29b-41d4-a716-446655440000")


# Error response examples for OpenAPI
ERROR_EXAMPLES = {
    "VALIDATION_ERROR": {
        "summary": "Validation Error",
        "value": {
            "type": "https://eventflow.example.com/errors/validation_error",
            "title": "Validation Error",
            "status": 400,
            "detail": "UUID inválido",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "USER_NOT_FOUND": {
        "summary": "User Not Found",
        "value": {
            "type": "https://eventflow.example.com/errors/user_not_found",
            "title": "Not Found",
            "status": 404,
            "detail": "Usuario no encontrado",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "EVENT_NOT_FOUND": {
        "summary": "Event Not Found",
        "value": {
            "type": "https://eventflow.example.com/errors/event_not_found",
            "title": "Not Found",
            "status": 404,
            "detail": "Evento no encontrado",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "INSUFFICIENT_INVENTORY": {
        "summary": "Insufficient Inventory",
        "value": {
            "type": "https://eventflow.example.com/errors/insufficient_inventory",
            "title": "Conflict",
            "status": 409,
            "detail": "Inventario insuficiente. Disponibles: 5",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "IDEMPOTENCY_CONFLICT": {
        "summary": "Idempotency Conflict",
        "value": {
            "type": "https://eventflow.example.com/errors/idempotency_conflict",
            "title": "Conflict",
            "status": 409,
            "detail": "Reserva ya procesada",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "PAYMENT_FAILED": {
        "summary": "Payment Failed",
        "value": {
            "type": "https://eventflow.example.com/errors/payment_failed",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "Error procesando pago: Redis connection failed",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "RESERVATION_FAILED": {
        "summary": "Reservation Failed",
        "value": {
            "type": "https://eventflow.example.com/errors/reservation_failed",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "Error confirmando reserva: MongoDB connection failed",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "INTERNAL_ERROR": {
        "summary": "Internal Error",
        "value": {
            "type": "https://eventflow.example.com/errors/internal_error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "Error inesperado en SAGA: ...",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
    "SERVICE_UNAVAILABLE": {
        "summary": "Service Unavailable",
        "value": {
            "type": "https://eventflow.example.com/errors/service_unavailable",
            "title": "Service Unavailable",
            "status": 503,
            "detail": "Usuarios Service circuit breaker open",
            "instance": "/api/v1/reservar",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    },
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting Reservas Service...")

    # Initialize databases
    await init_mongodb_indexes()
    logger.info("MongoDB indexes initialized")

    await register_lua_scripts()
    logger.info("Redis Lua scripts registered")

    await init_pg_schema()
    logger.info("PostgreSQL schema initialized")

    logger.info("Reservas Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Reservas Service...")
    await close_mongodb_connection()
    await close_redis_connection()
    await close_pg_pool()
    await close_http_clients()
    logger.info("Reservas Service shut down complete")


def custom_openapi():
    """Customize OpenAPI schema with RFC 7807 error responses."""
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title="Reservas & Pagos Service",
        version="1.0.0",
        description="Orquestador SAGA con Chain of Responsibility para reservas y pagos",
        routes=app.routes,
    )

    # Add RFC 7807 error response schema
    openapi_schema["components"]["schemas"]["RFC7807Error"] = RFC7807Error.model_json_schema()
    openapi_schema["components"]["schemas"]["RFC7807Error"]["example"] = ERROR_EXAMPLES["VALIDATION_ERROR"]["value"]

    # Add error response examples to all endpoints
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                responses = operation.get("responses", {})
                # Add RFC 7807 error responses to common status codes
                for status_code, example_key in [
                    ("400", "VALIDATION_ERROR"),
                    ("404", "USER_NOT_FOUND"),
                    ("409", "INSUFFICIENT_INVENTORY"),
                    ("500", "INTERNAL_ERROR"),
                    ("503", "SERVICE_UNAVAILABLE"),
                ]:
                    if status_code in responses:
                        responses[status_code]["content"] = {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RFC7807Error"},
                                "examples": {example_key: ERROR_EXAMPLES[example_key]}
                            }
                        }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app = FastAPI(
    title="Reservas & Pagos Service",
    description="Orquestador SAGA con Chain of Responsibility para reservas y pagos",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Override OpenAPI schema
app.openapi = custom_openapi

# Middleware (order matters - outer to inner)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(TracingMiddleware)           # Extract correlation ID first
app.add_middleware(APIVersioningMiddleware)     # Versioning
app.add_middleware(RFC7807Middleware)           # Error formatting

# Include routes
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint with dependency status (3 states per dependency)."""
    import time
    from src.services.mongo import get_mongo_client
    from src.services.redis_pago import get_redis_client
    from src.services.postgresql import get_pg_pool
    from src.services.http_clients import get_circuit_breaker_state, get_usuarios_client, get_eventos_client

    checks = {}
    overall_status = "healthy"

    # MongoDB
    try:
        start = time.perf_counter()
        client = await get_mongo_client()
        await client.admin.command("ping")
        latency_ms = (time.perf_counter() - start) * 1000
        if latency_ms > 100:
            checks["mongodb"] = "degraded"
            overall_status = "degraded" if overall_status == "healthy" else overall_status
        else:
            checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = "down"
        overall_status = "unhealthy"

    # Redis
    try:
        start = time.perf_counter()
        client = await get_redis_client()
        await client.ping()
        latency_ms = (time.perf_counter() - start) * 1000
        if latency_ms > 50:
            checks["redis"] = "degraded"
            overall_status = "degraded" if overall_status == "healthy" else overall_status
        else:
            checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = "down"
        overall_status = "unhealthy"

    # PostgreSQL
    try:
        start = time.perf_counter()
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        latency_ms = (time.perf_counter() - start) * 1000
        if latency_ms > 100:
            checks["postgresql"] = "degraded"
            overall_status = "degraded" if overall_status == "healthy" else overall_status
        else:
            checks["postgresql"] = "ok"
    except Exception as e:
        checks["postgresql"] = "down"
        overall_status = "unhealthy"

    # External services (HTTP clients) - circuit breaker states
    cb_states = get_circuit_breaker_state()
    for service, state in cb_states.items():
        if state == "open":
            checks[service] = "down"
            overall_status = "unhealthy"
        elif state == "half-open":
            checks[service] = "degraded"
            overall_status = "degraded" if overall_status == "healthy" else overall_status
        else:
            checks[service] = "ok"

    # HTTP client health checks (active)
    for service_name, client_factory in [
        ("usuarios_service", get_usuarios_client),
        ("eventos_service", get_eventos_client)
    ]:
        try:
            start = time.perf_counter()
            client = await client_factory()
            # Use a quick health check endpoint
            response = await client.get("/health", timeout=2.0)
            latency_ms = (time.perf_counter() - start) * 1000
            if response.status_code == 200:
                if latency_ms > 2000:  # 2s threshold for external services
                    checks[service_name] = "degraded"
                    overall_status = "degraded" if overall_status == "healthy" else overall_status
                else:
                    checks[service_name] = "ok"
            else:
                checks[service_name] = "degraded"
                overall_status = "degraded" if overall_status == "healthy" else overall_status
        except Exception as e:
            checks[service_name] = "down"
            overall_status = "unhealthy"

    return {
        "status": overall_status,
        "checks": checks,
        "service": "reservas-service",
        "version": "1.0.0",
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)