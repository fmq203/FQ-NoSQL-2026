import logging
import json
import sys


def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": record.levelname,
                "service": "reservas-service",
                "message": record.getMessage(),
            }

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

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.getLevelName(level.upper()))
    root_logger.handlers = [handler]

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)