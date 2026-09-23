"""RFC 7807 error response middleware for Reservas Service."""
import logging
from typing import Optional
from uuid import uuid4
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Error code mappings
ERROR_CODES = {
    400: "VALIDATION_ERROR",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}

ERROR_TITLES = {
    "VALIDATION_ERROR": "Validation Error",
    "NOT_FOUND": "Not Found",
    "CONFLICT": "Conflict",
    "INTERNAL_ERROR": "Internal Server Error",
    "SERVICE_UNAVAILABLE": "Service Unavailable",
    "USER_NOT_FOUND": "Not Found",
    "EVENT_NOT_FOUND": "Not Found",
    "INSUFFICIENT_INVENTORY": "Conflict",
    "IDEMPOTENCY_CONFLICT": "Conflict",
    "PAYMENT_FAILED": "Internal Server Error",
    "RESERVATION_FAILED": "Internal Server Error",
}


class RFC7807Middleware(BaseHTTPMiddleware):
    """Middleware to format all errors as RFC 7807 Problem Details."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            return self._format_error(request, e)

    def _format_error(self, request: Request, exc: Exception) -> JSONResponse:
        """Format exception as RFC 7807 Problem Details."""
        # Get correlation_id from request headers or generate new
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))

        # Determine status code and error code
        status_code = getattr(exc, "status_code", 500)
        error_code = getattr(exc, "error_code", ERROR_CODES.get(status_code, "INTERNAL_ERROR"))

        # Get detail message
        detail = str(exc)
        if hasattr(exc, "detail"):
            detail = exc.detail

        # Build RFC 7807 response
        problem = {
            "type": f"https://eventflow.example.com/errors/{error_code.lower()}",
            "title": ERROR_TITLES.get(error_code, "Error"),
            "status": status_code,
            "detail": detail,
            "instance": str(request.url.path),
            "correlation_id": correlation_id,
        }

        # Log error
        logger.error(
            f"RFC7807 Error: {error_code} - {detail}",
            extra={
                "correlation_id": correlation_id,
                "instance": str(request.url.path),
                "status_code": status_code,
                "error_code": error_code,
            }
        )

        response = JSONResponse(
            content=problem,
            status_code=status_code,
            headers={"X-Correlation-ID": correlation_id}
        )
        return response


# Custom exception classes for specific error codes
class RFC7807Exception(Exception):
    """Base exception with RFC 7807 properties."""

    def __init__(self, detail: str, status_code: int = 500, error_code: str = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code


class ValidationError(RFC7807Exception):
    """400/422 Validation Error."""
    def __init__(self, detail: str):
        super().__init__(detail, 422, "VALIDATION_ERROR")


class NotFoundError(RFC7807Exception):
    """404 Not Found."""
    def __init__(self, detail: str, error_code: str = "NOT_FOUND"):
        super().__init__(detail, 404, error_code)


class ConflictError(RFC7807Exception):
    """409 Conflict."""
    def __init__(self, detail: str, error_code: str = "CONFLICT"):
        super().__init__(detail, 409, error_code)


class ServiceUnavailableError(RFC7807Exception):
    """503 Service Unavailable."""
    def __init__(self, detail: str):
        super().__init__(detail, 503, "SERVICE_UNAVAILABLE")


class InternalError(RFC7807Exception):
    """500 Internal Server Error."""
    def __init__(self, detail: str):
        super().__init__(detail, 500, "INTERNAL_ERROR")


# Specific error classes
class UserNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("Usuario no encontrado", "USER_NOT_FOUND")


class EventNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("Evento no encontrado", "EVENT_NOT_FOUND")


class InsufficientInventoryError(ConflictError):
    def __init__(self, disponibles: int):
        super().__init__(f"Inventario insuficiente. Disponibles: {disponibles}", "INSUFFICIENT_INVENTORY")


class IdempotencyConflictError(ConflictError):
    def __init__(self):
        super().__init__("Reserva ya procesada", "IDEMPOTENCY_CONFLICT")


class PaymentFailedError(RFC7807Exception):
    def __init__(self, detail: str):
        super().__init__(detail, 500, "PAYMENT_FAILED")


class ReservationFailedError(RFC7807Exception):
    def __init__(self, detail: str):
        super().__init__(detail, 500, "RESERVATION_FAILED")