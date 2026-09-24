from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from uuid import UUID, uuid4
import logging

logger = logging.getLogger(__name__)

ERROR_TYPE_BASE = "https://eventflow.example.com/errors"

ERROR_CODES = {
    "VALIDATION_ERROR": f"{ERROR_TYPE_BASE}/validation-error",
    "NOT_FOUND": f"{ERROR_TYPE_BASE}/not-found",
    "DUPLICATE_EVENT": f"{ERROR_TYPE_BASE}/duplicate-event",
    "INTERNAL_ERROR": f"{ERROR_TYPE_BASE}/internal-error",
    "SERVICE_UNAVAILABLE": f"{ERROR_TYPE_BASE}/service-unavailable",
}

ERROR_TITLES = {
    "VALIDATION_ERROR": "Validation Error",
    "NOT_FOUND": "Not Found",
    "DUPLICATE_EVENT": "Conflict",
    "INTERNAL_ERROR": "Internal Server Error",
    "SERVICE_UNAVAILABLE": "Service Unavailable",
}


class EventFlowHTTPException(Exception):
    def __init__(
        self,
        error_code: str,
        detail: str,
        status_code: int,
        instance: str,
        correlation_id: UUID | None = None,
    ):
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        self.instance = instance
        self.correlation_id = correlation_id or uuid4()
        super().__init__(detail)


def create_error_response(
    error_code: str,
    detail: str,
    status_code: int,
    instance: str,
    correlation_id: UUID,
) -> JSONResponse:
    error_type = ERROR_CODES.get(error_code, ERROR_CODES["INTERNAL_ERROR"])
    title = ERROR_TITLES.get(error_code, "Internal Server Error")
    
    content = {
        "type": error_type,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "correlation_id": str(correlation_id),
    }
    
    headers = {
        "X-Correlation-ID": str(correlation_id),
        "X-Trace-ID": str(correlation_id),
    }
    
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
    )


async def eventflow_exception_handler(request: Request, exc: EventFlowHTTPException) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", uuid4())
    logger.warning(
        f"EventFlow HTTP exception: {exc.error_code}",
        extra={
            "correlation_id": str(correlation_id),
            "error_code": exc.error_code,
            "detail": exc.detail,
            "instance": exc.instance,
        },
    )
    return create_error_response(
        exc.error_code,
        exc.detail,
        exc.status_code,
        exc.instance,
        correlation_id,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", uuid4())
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")
    detail = "; ".join(errors)
    
    logger.warning(
        f"Validation error: {detail}",
        extra={
            "correlation_id": str(correlation_id),
            "errors": errors,
        },
    )
    return create_error_response(
        "VALIDATION_ERROR",
        detail,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        str(request.url.path),
        correlation_id,
    )


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", uuid4())
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")
    detail = "; ".join(errors)
    
    logger.warning(
        f"Pydantic validation error: {detail}",
        extra={
            "correlation_id": str(correlation_id),
            "errors": errors,
        },
    )
    return create_error_response(
        "VALIDATION_ERROR",
        detail,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        str(request.url.path),
        correlation_id,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", uuid4())
    
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        error_code = "NOT_FOUND"
        detail = exc.detail if isinstance(exc.detail, str) else "Not Found"
    else:
        error_code = "INTERNAL_ERROR"
        detail = exc.detail if isinstance(exc.detail, str) else "Internal Server Error"
    
    logger.warning(
        f"HTTP exception: {exc.status_code}",
        extra={
            "correlation_id": str(correlation_id),
            "status_code": exc.status_code,
            "detail": detail,
        },
    )
    return create_error_response(
        error_code,
        detail,
        exc.status_code,
        str(request.url.path),
        correlation_id,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", uuid4())
    
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={
            "correlation_id": str(correlation_id),
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )
    return create_error_response(
        "INTERNAL_ERROR",
        "An unexpected error occurred",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        str(request.url.path),
        correlation_id,
    )