from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


class EventFlowException(Exception):
    """Excepción base para EventFlow."""
    def __init__(
        self,
        error_code: str,
        title: str,
        status_code: int,
        detail: str,
        instance: str = ""
    ):
        self.error_code = error_code
        self.title = title
        self.status_code = status_code
        self.detail = detail
        self.instance = instance
        self.correlation_id = str(uuid4())
        super().__init__(detail)


class EventFlowHTTPException(EventFlowException):
    """Excepción HTTP con formato RFC 7807."""
    pass


def create_error_response(
    error_code: str,
    title: str,
    status_code: int,
    detail: str,
    instance: str,
    correlation_id: str
) -> dict:
    """Crear respuesta de error en formato RFC 7807."""
    return {
        "type": f"https://eventflow.example.com/errors/{error_code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "correlation_id": correlation_id
    }


async def eventflow_exception_handler(request: Request, exc: EventFlowHTTPException) -> JSONResponse:
    """Manejador para excepciones EventFlow."""
    error_response = create_error_response(
        error_code=exc.error_code,
        title=exc.title,
        status_code=exc.status_code,
        detail=exc.detail,
        instance=exc.instance or str(request.url.path),
        correlation_id=exc.correlation_id
    )
    response = JSONResponse(status_code=exc.status_code, content=error_response)
    response.headers["X-Correlation-ID"] = exc.correlation_id
    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Manejador para errores de validación de FastAPI."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    detail = "; ".join([f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors()])
    error_response = create_error_response(
        error_code="validation-error",
        title="Validation Error",
        status_code=422,
        detail=detail,
        instance=str(request.url.path),
        correlation_id=correlation_id
    )
    response = JSONResponse(status_code=422, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Manejador para errores de validación de Pydantic."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    error_response = create_error_response(
        error_code="validation-error",
        title="Validation Error",
        status_code=422,
        detail=str(exc),
        instance=str(request.url.path),
        correlation_id=correlation_id
    )
    response = JSONResponse(status_code=422, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Manejador para HTTPException de Starlette."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    
    if exc.status_code == 404:
        error_code = "not-found"
        title = "Not Found"
    elif exc.status_code == 409:
        error_code = "duplicate-resource"
        title = "Conflict"
    elif exc.status_code == 503:
        error_code = "service-unavailable"
        title = "Service Unavailable"
    else:
        error_code = "http-error"
        title = "HTTP Error"
    
    error_response = create_error_response(
        error_code=error_code,
        title=title,
        status_code=exc.status_code,
        detail=exc.detail,
        instance=str(request.url.path),
        correlation_id=correlation_id
    )
    response = JSONResponse(status_code=exc.status_code, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Manejador para excepciones genéricas."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    logger.exception(f"Error no manejado: {exc}")
    error_response = create_error_response(
        error_code="internal-error",
        title="Internal Server Error",
        status_code=500,
        detail="Error interno del servidor",
        instance=str(request.url.path),
        correlation_id=correlation_id
    )
    response = JSONResponse(status_code=500, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Registrar todos los manejadores de excepciones."""
    app.add_exception_handler(EventFlowHTTPException, eventflow_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)