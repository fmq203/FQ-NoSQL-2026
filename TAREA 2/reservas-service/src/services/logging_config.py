"""Structured JSON logging configuration for Reservas Service."""
import os
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

# Custom JSON formatter
class JSONFormatter(logging.Formatter):
    """JSON log formatter with required fields."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "reservas-service",
            "message": record.getMessage(),
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