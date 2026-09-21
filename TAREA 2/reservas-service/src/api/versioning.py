"""API versioning middleware for Reservas Service."""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import re


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """Middleware to handle API versioning via URL path and Accept header."""
    
    SUPPORTED_VERSIONS = ["v1"]
    DEFAULT_VERSION = "v1"
    VERSION_HEADER = "Accept"
    VERSION_REGEX = re.compile(r'application/vnd\.eventflow\.v(\d+)\+json')
    
    async def dispatch(self, request: Request, call_next):
        # Extract version from URL path
        path_version = self._extract_version_from_path(request.url.path)
        
        # Extract version from Accept header
        header_version = self._extract_version_from_header(request.headers.get("Accept", ""))
        
        # Determine version (path takes precedence)
        version = path_version or header_version or self.DEFAULT_VERSION
        
        # Validate version
        if version not in self.SUPPORTED_VERSIONS:
            return JSONResponse(
                content={
                    "type": "https://eventflow.example.com/errors/version_not_supported",
                    "title": "API Version Not Supported",
                    "status": 400,
                    "detail": f"API version '{version}' not supported. Supported: {self.SUPPORTED_VERSIONS}",
                    "instance": str(request.url.path),
                },
                status_code=400
            )
        
        # Add version to request state
        request.state.api_version = version
        
        response = await call_next(request)
        
        # Add version headers
        response.headers["X-API-Version"] = version
        response.headers["X-API-Deprecated"] = "false"
        
        return response
    
    def _extract_version_from_path(self, path: str) -> str:
        """Extract version from URL path (e.g., /api/v1/...)."""
        import re
        match = re.match(r'^/api/(v\d+)', path)
        if match:
            return match.group(1)
        return None
    
    def _extract_version_from_header(self, accept_header: str) -> str:
        """Extract version from Accept header."""
        match = self.VERSION_REGEX.search(accept_header)
        if match:
            return f"v{match.group(1)}"
        return None


def get_api_version(request: Request) -> str:
    """Get API version from request state."""
    return getattr(request.state, "api_version", "v1")