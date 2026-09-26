import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class EventFlowException(Exception):
    """Excepcion base de dominio para EventFlow (no necesariamente HTTP)."""

    def __init__(
        self,
        error_code: str,
        title: str,
        status_code: int,
        detail: str,
        instance: str = "",
    ):
        self.error_code = error_code
        self.title = title
        self.status_code = status_code
        self.detail = detail
        self.instance = instance
        self.correlation_id = str(uuid4())
        super().__init__(detail)


class EventFlowHTTPException(EventFlowException):
    """Excepcion HTTP con formato RFC 7807, propia de este servicio."""


def create_error_response(
    error_code: str,
    title: str,
    status_code: int,
    detail: str,
    instance: str,
    correlation_id: str,
) -> dict:
    """Respuesta de error en formato RFC 7807."""
    return {
        "type": f"https://eventflow.example.com/errors/{error_code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "correlation_id": correlation_id,
    }


async def eventflow_exception_handler(request: Request, exc: EventFlowHTTPException) -> JSONResponse:
    """Manejador para EventFlowHTTPException (404/409/422/503 propios del dominio)."""
    correlation_id = getattr(request.state, "correlation_id", exc.correlation_id)
    error_response = create_error_response(
        error_code=exc.error_code,
        title=exc.title,
        status_code=exc.status_code,
        detail=exc.detail,
        instance=exc.instance or str(request.url.path),
        correlation_id=correlation_id,
    )
    response = JSONResponse(status_code=exc.status_code, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Manejador para errores 422 de validacion de FastAPI/Pydantic."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    error_response = create_error_response(
        error_code="VALIDATION_ERROR",
        title="Validation Error",
        status_code=422,
        detail=detail,
        instance=str(request.url.path),
        correlation_id=correlation_id,
    )
    response = JSONResponse(status_code=422, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    error_response = create_error_response(
        error_code="VALIDATION_ERROR",
        title="Validation Error",
        status_code=422,
        detail=str(exc),
        instance=str(request.url.path),
        correlation_id=correlation_id,
    )
    response = JSONResponse(status_code=422, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Manejador para HTTPException de Starlette (404 de ruta inexistente, etc)."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    error_codes = {404: "NOT_FOUND", 409: "CONFLICT", 503: "SERVICE_UNAVAILABLE"}
    error_code = error_codes.get(exc.status_code, "HTTP_ERROR")
    error_response = create_error_response(
        error_code=error_code,
        title=str(exc.detail) if exc.detail else "HTTP Error",
        status_code=exc.status_code,
        detail=str(exc.detail),
        instance=str(request.url.path),
        correlation_id=correlation_id,
    )
    response = JSONResponse(status_code=exc.status_code, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Manejador de ultimo recurso para excepciones no anticipadas."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    logger.exception(f"Error no manejado: {exc}")
    error_response = create_error_response(
        error_code="INTERNAL_ERROR",
        title="Internal Server Error",
        status_code=500,
        detail="Error interno del servidor",
        instance=str(request.url.path),
        correlation_id=correlation_id,
    )
    response = JSONResponse(status_code=500, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Registrar todos los manejadores de excepciones, en orden mas
    especifico a mas generico (FastAPI/Starlette resuelven por MRO)."""
    app.add_exception_handler(EventFlowHTTPException, eventflow_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
