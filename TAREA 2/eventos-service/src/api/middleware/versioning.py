"""
API Versioning Middleware - Placeholder for v2

Accept header parsing (application/vnd.eventflow.v1+json) deferred to v2.
Current MVP uses URL path versioning (/api/v1/) only.

Future implementation should:
- Parse Accept header for version negotiation
- Support Deprecation and Sunset headers
- Return appropriate version in response
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """
    Placeholder middleware for API version negotiation via Accept header.

    Not implemented in MVP - URL path versioning (/api/v1/) is sufficient.
    Deferred to v2 per specification.
    """

    async def dispatch(self, request: Request, call_next):
        # TODO: Implement Accept header parsing for version negotiation
        # Example: Accept: application/vnd.eventflow.v1+json
        response = await call_next(request)
        return response