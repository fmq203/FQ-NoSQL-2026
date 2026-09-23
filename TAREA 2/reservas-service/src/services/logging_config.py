"""Structured JSON logging configuration for Reservas Service."""
import os
import json
import logging
import sys
import re
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4


# PII patterns to sanitize
PII_PATTERNS = {
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
    "dni": re.compile(r'\b\d{7,8}[A-Za-z]?\b'),  # Spanish DNI/NIE
    "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
    "iban": re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b'),
    "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
}


def sanitize_pii(text: str) -> str:
    """Sanitize PII from log messages."""
    if not isinstance(text, str):
        return text
    
    sanitized = text
    for pii_type, pattern in PII_PATTERNS.items():
        sanitized = pattern.sub(f"[REDACTED_{pii_type.upper()}]", sanitized)
    
    return sanitized


class PIISanitizingFilter(logging.Filter):
    """Logging filter to sanitize PII from log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Sanitize the log message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = sanitize_pii(record.msg)
        
        # Sanitize extra fields that might contain PII
        for key, value in record.__dict__.items():
            if isinstance(value, str) and key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                                                      'levelname', 'levelno', 'lineno', 'module', 'msecs',
                                                      'message', 'name', 'pathname', 'process', 'processName',
                                                      'relativeCreated', 'thread', 'threadName', 'exc_info',
                                                      'exc_text', 'stack_info', 'correlation_id', 'span_id',
                                                      'trace_id', 'reserva_id', 'saga_step', 'operation',
                                                      'duration_ms', 'compensation_triggered', 'cache_hit']:
                if not key.startswith("_"):
                    setattr(record, key, sanitize_pii(value))
        
        return True


# Custom JSON formatter
class JSONFormatter(logging.Formatter):
    """JSON log formatter with required fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "reservas-service",
            "message": sanitize_pii(record.getMessage()),
        }

        # Add correlation_id if present
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
            log_data["trace_id"] = record.correlation_id
        else:
            log_data["correlation_id"] = getattr(record, "correlation_id", str(uuid4()))
            log_data["trace_id"] = log_data["correlation_id"]

        if hasattr(record, "span_id"):
            log_data["span_id"] = record.span_id
        else:
            log_data["span_id"] = str(uuid4())

        # Add context fields
        context = {}
        for attr in ["reserva_id", "saga_step", "operation", "duration_ms", "compensation_triggered", "cache_hit"]:
            if hasattr(record, attr):
                context[attr] = getattr(record, attr)

        if context:
            log_data["context"] = context

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "msg", "name", "pathname", "process",
                          "processName", "relativeCreated", "thread", "threadName",
                          "exc_info", "exc_text", "stack_info", "correlation_id", "span_id"]:
                if not key.startswith("_"):
                    log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """Configure structured JSON logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json")

    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    # Add PII sanitizing filter
    root_logger.addFilter(PIISanitizingFilter())

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.addHandler(console_handler)

    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding correlation_id and other context to logs."""

    def __init__(self, correlation_id: str = None, **extra):
        self.correlation_id = correlation_id or str(uuid4())
        self.extra = extra
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            record.correlation_id = self.correlation_id
            for key, value in self.extra.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, *args):
        logging.setLogRecordFactory(self.old_factory)


def log_saga_step(
    logger: logging.Logger,
    level: int,
    message: str,
    correlation_id: str,
    reserva_id: str = None,
    saga_step: str = None,
    operation: str = "saga_execute",
    duration_ms: int = None,
    compensation_triggered: bool = False,
    **extra
) -> None:
    """Log SAGA step with required fields."""
    extra_fields = {
        "correlation_id": correlation_id,
        "operation": operation,
    }
    if reserva_id:
        extra_fields["reserva_id"] = reserva_id
    if saga_step:
        extra_fields["saga_step"] = saga_step
    if duration_ms is not None:
        extra_fields["duration_ms"] = duration_ms
    extra_fields["compensation_triggered"] = compensation_triggered
    extra_fields.update(extra)

    logger.log(level, message, extra=extra_fields)