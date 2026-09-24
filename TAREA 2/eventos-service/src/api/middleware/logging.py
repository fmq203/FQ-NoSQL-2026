import json
import logging
import time
import sys
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from uuid import UUID, uuid4
from typing import Optional


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger_name: str = "eventos-service"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        correlation_id = getattr(request.state, "correlation_id", uuid4())
        trace_id = getattr(request.state, "trace_id", correlation_id)
        span_id = uuid4()

        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id
        request.state.span_id = span_id

        self._log_request(request, correlation_id, trace_id, span_id)

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            self._log_response(
                request, response, correlation_id, trace_id, span_id, duration_ms
            )

            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_exception(request, exc, correlation_id, trace_id, span_id, duration_ms)
            raise

    def _log_request(self, request: Request, correlation_id: UUID, trace_id: UUID, span_id: UUID):
        self.logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                "correlation_id": str(correlation_id),
                "trace_id": str(trace_id),
                "span_id": str(span_id),
                "log_message": f"Incoming request: {request.method} {request.url.path}",
                "context": {
                    "operation": f"{request.method.lower()}_{request.url.path.strip('/').replace('/', '_') or 'root'}",
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                },
            },
        )

    def _log_response(
        self,
        request: Request,
        response: Response,
        correlation_id: UUID,
        trace_id: UUID,
        span_id: UUID,
        duration_ms: float,
    ):
        level = logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING

        self.logger.log(
            level,
            f"Response: {response.status_code} for {request.method} {request.url.path}",
            extra={
                "correlation_id": str(correlation_id),
                "trace_id": str(trace_id),
                "span_id": str(span_id),
                "log_message": f"Response: {response.status_code} for {request.method} {request.url.path}",
                "context": {
                    "operation": f"{request.method.lower()}_{request.url.path.strip('/').replace('/', '_') or 'root'}",
                    "duration_ms": round(duration_ms, 2),
                    "status_code": response.status_code,
                },
            },
        )

    def _log_exception(
        self,
        request: Request,
        exc: Exception,
        correlation_id: UUID,
        trace_id: UUID,
        span_id: UUID,
        duration_ms: float,
    ):
        self.logger.error(
            f"Exception in {request.method} {request.url.path}: {type(exc).__name__}: {exc}",
            extra={
                "correlation_id": str(correlation_id),
                "trace_id": str(trace_id),
                "span_id": str(span_id),
                "log_message": f"Exception in {request.method} {request.url.path}: {type(exc).__name__}: {exc}",
                "context": {
                    "operation": f"{request.method.lower()}_{request.url.path.strip('/').replace('/', '_') or 'root'}",
                    "duration_ms": round(duration_ms, 2),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
            },
            exc_info=True,
        )


def setup_json_logging(log_level: str = "INFO"):
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.handlers = [handler]

    logging.getLogger("uvicorn").handlers = [handler]
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": "eventos-service",
            "correlation_id": getattr(record, "correlation_id", None),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
            "message": record.getMessage(),
            "context": getattr(record, "context", {}),
        }

        if log_entry["correlation_id"] is None:
            del log_entry["correlation_id"]
        if log_entry["trace_id"] is None:
            del log_entry["trace_id"]
        if log_entry["span_id"] is None:
            del log_entry["span_id"]
        if not log_entry["context"]:
            del log_entry["context"]

        return json.dumps(log_entry, ensure_ascii=False)