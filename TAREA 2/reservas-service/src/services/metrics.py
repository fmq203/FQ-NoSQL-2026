"""Prometheus metrics for Reservas Service."""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# Create a custom registry to avoid conflicts
REGISTRY = CollectorRegistry()

# SAGA Metrics
saga_duration_seconds = Histogram(
    'saga_duration_seconds',
    'Latency per SAGA step',
    ['step', 'status'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registry=REGISTRY
)

saga_total = Counter(
    'saga_total',
    'Total SAGA executions',
    ['status'],
    registry=REGISTRY
)

saga_compensation_total = Counter(
    'saga_compensation_total',
    'Compensations triggered per step',
    ['step'],
    registry=REGISTRY
)

# HTTP Metrics
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'path', 'status'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registry=REGISTRY
)

# Database Metrics
db_operation_duration_seconds = Histogram(
    'db_operation_duration_seconds',
    'Database operation latency',
    ['db', 'operation', 'status'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registry=REGISTRY
)

# Circuit Breaker Metrics
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['service', 'state'],
    registry=REGISTRY
)

# Idempotency Metrics
idempotency_hit_total = Counter(
    'idempotency_hit_total',
    'Idempotent request hits',
    registry=REGISTRY
)

# State mapping for circuit breaker gauge
CB_STATE_MAP = {
    'closed': 0,
    'open': 1,
    'half-open': 2,
}


def record_saga_step_duration(step: str, status: str, duration: float) -> None:
    """Record SAGA step duration."""
    saga_duration_seconds.labels(step=step, status=status).observe(duration)


def record_saga_total(status: str) -> None:
    """Record SAGA execution total."""
    saga_total.labels(status=status).inc()


def record_saga_compensation(step: str) -> None:
    """Record SAGA compensation."""
    saga_compensation_total.labels(step=step).inc()


def record_http_request_duration(method: str, path: str, status: int, duration: float) -> None:
    """Record HTTP request duration."""
    http_request_duration_seconds.labels(method=method, path=path, status=str(status)).observe(duration)


def record_db_operation_duration(db: str, operation: str, status: str, duration: float) -> None:
    """Record database operation duration."""
    db_operation_duration_seconds.labels(db=db, operation=operation, status=status).observe(duration)


def set_circuit_breaker_state(service: str, state: str) -> None:
    """Set circuit breaker state gauge."""
    # Reset all states for this service
    for s in CB_STATE_MAP:
        circuit_breaker_state.labels(service=service, state=s).set(0)
    # Set the active state
    if state in CB_STATE_MAP:
        circuit_breaker_state.labels(service=service, state=state).set(1)


def record_idempotency_hit() -> None:
    """Record idempotent request hit."""
    idempotency_hit_total.inc()


def get_registry() -> CollectorRegistry:
    """Get the metrics registry."""
    return REGISTRY