from fastapi import FastAPI, Request
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


class EventFlowHTTPException(Exception):
    """Excepción HTTP con formato RFC 7807."""
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


class RFC7807Middleware:
    """Middleware para formatear errores como RFC 7807."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                if status_code >= 400:
                    # Solo interceptar errores que no tengan body ya
                    pass
            await send(message)

        await self.app(scope, receive, send_wrapper)


async def eventflow_exception_handler(request, exc: Exception) -> JSONResponse:
    """Manejador para excepciones EventFlow."""
    if hasattr(exc, 'error_code'):
        error_code = exc.error_code
        title = exc.title
        status_code = exc.status_code
        detail = exc.detail
        instance = exc.instance
        correlation_id = exc.correlation_id
    else:
        error_code = "internal-error"
        title = "Internal Server Error"
        status_code = 500
        detail = str(exc)
        instance = ""
        correlation_id = str(uuid4())

    error_response = create_error_response(
        error_code=error_code,
        title=title,
        status_code=status_code,
        detail=detail,
        instance=instance or "",
        correlation_id=correlation_id
    )
    response = JSONResponse(status_code=status_code, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def validation_exception_handler(request, exc: Exception) -> JSONResponse:
    """Manejador para errores de validación."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    detail = str(exc)
    error_response = create_error_response(
        error_code="validation-error",
        title="Validation Error",
        status_code=422,
        detail=detail,
        instance="",
        correlation_id=correlation_id
    )
    response = JSONResponse(status_code=422, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def generic_exception_handler(request, exc: Exception) -> JSONResponse:
    """Manejador para excepciones genéricas."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    logger = logging.getLogger(__name__)
    logger.exception(f"Error no manejado: {exc}")
    error_response = {
        "type": "https://eventflow.example.com/errors/internal-error",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "Error interno del servidor",
        "instance": "",
        "correlation_id": correlation_id
    }
    response = JSONResponse(status_code=500, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


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


async def validation_exception_handler(request, exc: Exception) -> JSONResponse:
    """Manejador para errores de validación."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    detail = str(exc)
    error_response = create_error_response(
        error_code="validation-error",
        title="Validation Error",
        status_code=422,
        detail=detail,
        instance="",
        correlation_id=correlation_id
    )
    response = JSONResponse(status_code=422, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


async def generic_exception_handler(request, exc: Exception) -> JSONResponse:
    """Manejador para excepciones genéricas."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    logger = logging.getLogger(__name__)
    logger.exception(f"Error no manejado: {exc}")
    error_response = {
        "type": "https://eventflow.example.com/errors/internal-error",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "Error interno del servidor",
        "instance": "",
        "correlation_id": correlation_id
    }
    response = JSONResponse(status_code=500, content=error_response)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


def register_exception_handlers(app):
    """Registrar manejadores de excepciones."""
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app.add_exception_handler(Exception, generic_exception_handler)
    app.add_exception_handler(RequestValidationError, lambda r, e: validation_exception_handler(r, e))
    app.add_exception_handler(ValidationError, lambda r, e: validation_exception_handler(r, e))
    app.add_exception_handler(500, lambda r, e: generic_exception_handler(r, e))