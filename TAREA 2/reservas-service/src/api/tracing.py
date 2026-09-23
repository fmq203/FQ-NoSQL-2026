"""Distributed tracing middleware for Reservas Service."""
import logging
from uuid import uuid4
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

CORRELATION_HEADER = "X-Correlation-ID"
TRACE_HEADER = "X-Trace-ID"


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware to extract/propagate correlation IDs for distributed tracing."""

    async def dispatch(self, request: Request, call_next):
        # Extract or generate correlation ID
        correlation_id = request.headers.get(CORRELATION_HEADER)
        if not correlation_id:
            correlation_id = str(uuid4())

        # Extract or use correlation_id as trace_id
        trace_id = request.headers.get(TRACE_HEADER, correlation_id)

        # Add to request state for downstream use
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id

        # Add to logging context
        logging.getLogger().info(
            "Incoming request",
            extra={
                "correlation_id": correlation_id,
                "trace_id": trace_id,
                "span_id": str(uuid4()),
                "method": request.method,
                "path": request.url.path,
            }
        )

        response = await call_next(request)

        # Add correlation headers to response
        response.headers[CORRELATION_HEADER] = correlation_id
        response.headers[TRACE_HEADER] = trace_id

        return response


def get_correlation_id(request: Request) -> str:
    """Get correlation ID from request state."""
    return getattr(request.state, "correlation_id", str(uuid4()))


def get_trace_id(request: Request) -> str:
    """Get trace ID from request state."""
    return getattr(request.state, "trace_id", str(uuid4()))