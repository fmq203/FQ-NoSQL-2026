"""Main FastAPI application for Reservas Service."""
import os
import logging
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

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


app = FastAPI(
    title="Reservas & Pagos Service",
    description="Orquestador SAGA con Chain of Responsibility para reservas y pagos",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

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
    
    # External services (HTTP clients)
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