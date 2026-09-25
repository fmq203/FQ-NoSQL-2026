# Research: Eventos CRUD Service

## Technical Decisions

### 1. Motor Async Driver Configuration

**Decision**: Use Motor 3.3+ with AsyncIOMotorClient for MongoDB connectivity.

**Rationale**: 
- Constitution mandates Python 3.11 + FastAPI + Motor async
- Motor provides native async/await support for non-blocking I/O
- Replica set support built-in with read preference configuration

**Configuration**:
```python
client = AsyncIOMotorClient(
    mongodb_uri,
    readPreference='secondaryPreferred',  # For reads
    writeConcern=WriteConcern('majority', journal=True),
    maxPoolSize=10,
    minPoolSize=1,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    socketTimeoutMS=30000
)
```

**Alternatives Considered**:
- PyMongo (sync): Rejected - blocks event loop, violates async requirement
- Beanie ODM: Rejected - adds abstraction layer not justified for simple CRUD (YAGNI)

### 2. Pydantic v2 Models with Validation

**Decision**: Use Pydantic v2 (BaseModel, Field, field_validator, model_validator) for request/response models and domain validation.

**Rationale**:
- FastAPI native integration with Pydantic v2
- Built-in validation with custom validators for business rules
- Automatic OpenAPI schema generation

**Key Validations**:
- `aforo_total >= entradas_disponibles >= 0`
- `precios[]` categories unique within event
- `precio >= 0`, `disponibles >= 0`
- `sum(precios[].disponibles) <= entradas_disponibles`
- `estado` in enum: borrador, publicado, cancelado, finalizado
- `ubicacion.ciudad` and `ubicacion.pais` required, non-empty

### 3. Health Check Implementation

**Decision**: Implement health check with MongoDB `ping` command, measuring latency to determine status.

**Logic**:
- Ping MongoDB with 2-second timeout
- Latency < 50ms → `healthy` (mongodb: "ok")
- Latency 50-500ms → `degraded` (mongodb: "slow")
- Ping failed/timeout → `unhealthy` (mongodb: "down"), HTTP 503

**Rationale**:
- Constitution Principle IV: Observability by Default
- Kubernetes/Docker Compose readiness/liveness probe compatible
- Meets < 10ms p99 requirement for healthy state

### 4. RFC 7807 Error Handling

**Decision**: Implement custom exception handlers for all HTTP error codes returning Problem Details format.

**Error Mapping**:
| HTTP Status | Error Code | Type URI |
|-------------|------------|----------|
| 400 | VALIDATION_ERROR | https://eventflow.example.com/errors/validation-error |
| 404 | NOT_FOUND | https://eventflow.example.com/errors/not-found |
| 422 | VALIDATION_ERROR | https://eventflow.example.com/errors/validation-error |
| 500 | INTERNAL_ERROR | https://eventflow.example.com/errors/internal-error |
| 503 | SERVICE_UNAVAILABLE | https://eventflow.example.com/errors/service-unavailable |

**Implementation**: FastAPI exception handlers + custom `EventFlowHTTPException` class with correlation_id propagation.

### 5. Correlation ID Middleware

**Decision**: Middleware extracts/generates `X-Correlation-ID` header, adds to response headers and structured logging context.

**Flow**:
1. Ingress: Extract `X-Correlation-ID` or generate UUID v4
2. Store in request.state.correlation_id
3. Add to all structured log entries as `correlation_id` and `trace_id`
4. Egress: Add `X-Correlation-ID` and `X-Trace-ID` to response headers
5. Pass to downstream calls via httpx headers

### 6. Structured JSON Logging

**Decision**: Use Python `logging` with `json-logger` or custom JSON formatter.

**Schema** (per Constitution Principle IV):
```json
{
  "timestamp": "ISO8601",
  "level": "INFO|WARN|ERROR|DEBUG",
  "service": "eventos-service",
  "correlation_id": "uuid",
  "trace_id": "uuid",
  "span_id": "uuid",
  "message": "string",
  "context": {
    "evento_id": "uuid|optional",
    "operation": "create_event|get_event|health_check",
    "duration_ms": 45,
    "additional_fields": "..."
  }
}
```

### 7. MongoDB Indexes

**Decision**: Create indexes on startup for query performance.

**Indexes**:
```python
# Unique index on _id (automatic)
# Compound indexes for query patterns
await collection.create_index("nombre")
await collection.create_index("estado")
await collection.create_index("creado_en")
await collection.create_index([("estado", 1), ("creado_en", -1)])
```

### 8. Configuration Management

**Decision**: Use `pydantic-settings` with `.env` file support.

**Settings**:
```python
class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "eventflow"
    mongodb_collection: str = "eventos"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    health_check_timeout_ms: int = 2000
    health_check_degraded_threshold_ms: int = 50
    health_check_unhealthy_threshold_ms: int = 500
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### 9. Docker Configuration

**Decision**: Multi-stage Dockerfile for production, docker-compose for development.

**Dockerfile**:
```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY src/ ./src/
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10. Testing Strategy

**Contract Tests** (pytest + httpx + pytest-asyncio):
- Test each endpoint against OpenAPI schema
- Validate request/response formats
- Test error responses match RFC 7807

**Integration Tests**:
- Full CRUD flow with real MongoDB (testcontainers or test DB)
- Health check with real MongoDB connection
- Correlation ID propagation

**Unit Tests**:
- Model validation logic
- Service layer business logic
- Health check status determination

## Dependencies Summary

### Production
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
motor==3.3.2
pydantic==2.5.3
pydantic-settings==2.1.0
python-json-logger==2.0.7
python-dotenv==1.0.0
```

### Development/Test
```
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
pytest-cov==4.1.0
```

## Open Questions Resolved

1. **Authentication**: Not in MVP scope (per spec assumptions)
2. **Event name uniqueness**: Not required - only UUID is PK
3. **Soft deletes**: Not required - estado "cancelado" serves this purpose
4. **Pagination for GET /api/eventos**: Not in scope - only single GET by ID
5. **Update/Delete endpoints**: Not in MVP - only POST (create) and GET (read)