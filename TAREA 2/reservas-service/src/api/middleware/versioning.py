"""
API Versioning Middleware - Placeholder for v2

Accept header parsing deferred to v2. Current MVP uses URL path versioning (/api/v1/) only.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class APIVersioningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # TODO: Implement Accept header parsing for version negotiation
        # Example: Accept: application/vnd.eventflow.v1+json
        response = await call_next(request)
        return response