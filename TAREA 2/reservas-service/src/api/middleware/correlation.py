from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from uuid import UUID, uuid4
import re


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE
)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware para manejo de correlation IDs."""
    async def dispatch(self, request: Request, call_next):
        correlation_id = self._extract_correlation_id(request)

        request.state.correlation_id = correlation_id
        request.state.trace_id = correlation_id

        response = await call_next(request)

        response.headers["X-Correlation-ID"] = str(correlation_id)
        response.headers["X-Trace-ID"] = str(correlation_id)

        return response

    def _extract_correlation_id(self, request: Request) -> UUID:
        correlation_id = request.headers.get("X-Correlation-ID")
        if correlation_id and self._is_valid_uuid(correlation_id):
            return UUID(correlation_id)

        trace_id = request.headers.get("X-Trace-ID")
        if trace_id and self._is_valid_uuid(trace_id):
            return UUID(trace_id)

        return uuid4()

    def _is_valid_uuid(self, value: str) -> bool:
        return bool(UUID_PATTERN.match(value))