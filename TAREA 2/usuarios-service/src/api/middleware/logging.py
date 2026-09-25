import json
import logging
import time
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from uuid import uuid4


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para logging estructurado en JSON con correlation IDs."""

    def __init__(self, app, logger_name: str = "usuarios-service"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        correlation_id = getattr(request.state, "correlation_id", uuid4())
        trace_id = getattr(request.state, "trace_id", correlation_id)
        span_id = uuid4()

        # Log request entrante
        self._log_request(request, correlation_id, trace_id, span_id)

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log response saliente
            self._log_response(
                request, response, correlation_id, trace_id, span_id, duration_ms
            )

            # Añadir headers de tracing
            response.headers["X-Correlation-ID"] = str(correlation_id)
            response.headers["X-Trace-ID"] = str(trace_id)

            return response
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_error(request, e, correlation_id, trace_id, span_id, duration_ms)
            raise

    def _log_request(self, request: Request, correlation_id, trace_id, span_id):
        self.logger.info(
            "Request entrante",
            extra={
                "correlation_id": str(correlation_id),
                "trace_id": str(trace_id),
                "span_id": str(span_id),
                "log_message": f"Incoming {request.method} {request.url.path}",
                "context": {
                    "operation": f"{request.method} {request.url.path}",
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                },
            },
        )

    def _log_response(
        self, request: Request, response: Response, correlation_id, trace_id, span_id, duration_ms: float
    ):
        level = logging.INFO if response.status_code < 400 else logging.WARNING
        self.logger.log(
            level,
            "Response saliente",
            extra={
                "correlation_id": str(correlation_id),
                "trace_id": str(trace_id),
                "span_id": str(span_id),
                "log_message": f"Outgoing {request.method} {request.url.path} -> {response.status_code}",
                "context": {
                    "operation": f"{request.method} {request.url.path}",
                    "duration_ms": round(duration_ms, 2),
                    "status_code": response.status_code,
                },
            },
        )

    def _log_error(
        self, request: Request, error: Exception, correlation_id, trace_id, span_id, duration_ms: float
    ):
        self.logger.error(
            f"Error en request: {error}",
            extra={
                "correlation_id": str(correlation_id),
                "trace_id": str(trace_id),
                "span_id": str(span_id),
                "log_message": f"Error {request.method} {request.url.path}: {type(error).__name__}",
                "context": {
                    "operation": f"{request.method} {request.url.path}",
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                },
            },
            exc_info=True,
        )


def setup_json_logging(level: str = "INFO") -> None:
    """Configurar logging JSON estructurado."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": record.levelname,
                "service": "usuarios-service",
                "message": record.getMessage(),
            }

            # Añadir campos extra si existen
            if hasattr(record, "correlation_id"):
                log_data["correlation_id"] = record.correlation_id
            if hasattr(record, "trace_id"):
                log_data["trace_id"] = record.trace_id
            if hasattr(record, "span_id"):
                log_data["span_id"] = record.span_id
            if hasattr(record, "log_message"):
                log_data["log_message"] = record.log_message
            if hasattr(record, "context"):
                log_data["context"] = record.context

            return json.dumps(log_data, ensure_ascii=False)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Reducir ruido de librerías
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)