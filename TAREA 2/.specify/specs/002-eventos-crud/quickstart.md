# Quickstart: Eventos CRUD Service

## Prerequisites

- Python 3.11+
- MongoDB 7.0+ (replica set recommended)
- Docker & Docker Compose (for containerized deployment)
- uv or pip for dependency management

## Local Development Setup

### 1. Clone and Navigate
```bash
cd /home/fqueirolo/TECNOLOGO/NoSQL/TAREA 2/eventos-service
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your MongoDB URI and settings
```

**Required `.env` variables**:
```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=eventflow
MONGODB_COLLECTION=eventos
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
HEALTH_CHECK_TIMEOUT_MS=2000
HEALTH_CHECK_DEGRADED_THRESHOLD_MS=50
HEALTH_CHECK_UNHEALTHY_THRESHOLD_MS=500
```

### 5. Start MongoDB (if not running)
```bash
# Using Docker
docker run -d -p 27017:27017 --name mongo mongo:7.0

# Or use existing MongoDB instance
```

### 6. Run Service
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Service available at: `http://localhost:8000`

### 7. Verify Health Check
```bash
curl http://localhost:8000/health
```

Expected response (healthy):
```json
{
  "status": "healthy",
  "checks": {"mongodb": "ok"},
  "timestamp": "2026-09-23T10:00:00.000Z"
}
```

## API Usage Examples

### Create Event (POST /api/v1/eventos)

```bash
curl -X POST http://localhost:8000/api/v1/eventos \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "nombre": "Concierto Rock 2026",
    "estado": "publicado",
    "aforo_total": 5000,
    "entradas_disponibles": 5000,
    "precios": [
      {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
      {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
    ],
    "ubicacion": {
      "ciudad": "Buenos Aires",
      "pais": "Argentina",
      "direccion": "Estadio Luna Park"
    }
  }'
```

**Response (201 Created)**:
```json
{
  "evento_id": "550e8400-e29b-41d4-a716-446655440000",
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",
  "aforo_total": 5000,
  "entradas_disponibles": 5000,
  "precios": [
    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
  ],
  "ubicacion": {
    "ciudad": "Buenos Aires",
    "pais": "Argentina",
    "direccion": "Estadio Luna Park"
  },
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```

**Headers**: `X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000`

### Get Event by ID (GET /api/v1/eventos/{evento_id})

```bash
curl -X GET http://localhost:8000/api/v1/eventos/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440001"
```

**Response (200 OK)**:
```json
{
  "evento_id": "550e8400-e29b-41d4-a716-446655440000",
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",
  "aforo_total": 5000,
  "entradas_disponibles": 5000,
  "precios": [
    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
  ],
  "ubicacion": {
    "ciudad": "Buenos Aires",
    "pais": "Argentina",
    "direccion": "Estadio Luna Park"
  },
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```

### Health Check (GET /health)

```bash
curl -X GET http://localhost:8000/health
```

**Response (200 OK - healthy)**:
```json
{
  "status": "healthy",
  "checks": {"mongodb": "ok"},
  "timestamp": "2026-09-23T10:00:00.000Z"
}
```

**Response (200 OK - degraded)**:
```json
{
  "status": "degraded",
  "checks": {"mongodb": "slow"},
  "timestamp": "2026-09-23T10:00:00.000Z"
}
```

**Response (503 Service Unavailable - unhealthy)**:
```json
{
  "status": "unhealthy",
  "checks": {"mongodb": "down"},
  "timestamp": "2026-09-23T10:00:00.000Z"
}
```

## Error Response Examples

### Validation Error (422)
```json
{
  "type": "https://eventflow.example.com/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "entradas_disponibles cannot exceed aforo_total",
  "instance": "/api/v1/eventos",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Conflict - Duplicate Event (409)
```json
{
  "type": "https://eventflow.example.com/errors/duplicate-event",
  "title": "Conflict",
  "status": 409,
  "detail": "Evento duplicado (nombre ya existe)",
  "instance": "/api/v1/eventos",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Not Found (404)
```json
{
  "type": "https://eventflow.example.com/errors/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "Evento no encontrado",
  "instance": "/api/v1/eventos/550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

### Service Unavailable (503)
```json
{
  "type": "https://eventflow.example.com/errors/service-unavailable",
  "title": "Service Unavailable",
  "status": 503,
  "detail": "MongoDB connection failed",
  "instance": "/health",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440002"
}
```

## Running Tests

### All Tests
```bash
pytest
```

### With Coverage
```bash
pytest --cov=src --cov-report=term-missing --cov-report=html
```

### Specific Test Types
```bash
# Contract tests only
pytest tests/contract/

# Integration tests only
pytest tests/integration/

# Unit tests only
pytest tests/unit/
```

### Test with MongoDB (Integration)
```bash
# Ensure MongoDB is running
pytest tests/integration/ -v
```

## Docker Deployment

### Build Image
```bash
docker build -t eventos-service:latest .
```

### Run Container
```bash
docker run -d \
  --name eventos-service \
  -p 8000:8000 \
  -e MONGODB_URI=mongodb://host.docker.internal:27017 \
  -e MONGODB_DATABASE=eventflow \
  eventos-service:latest
```

### Docker Compose (Development)
```bash
# From repository root
docker-compose up -d eventos-service
```

## API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Troubleshooting

### MongoDB Connection Failed
1. Verify MongoDB is running: `docker ps | grep mongo`
2. Check URI in `.env`: `MONGODB_URI`
3. Verify network connectivity: `telnet localhost 27017`

### Health Check Returns Unhealthy
1. Check MongoDB logs: `docker logs mongo`
2. Verify replica set status if using replica set
3. Increase `HEALTH_CHECK_TIMEOUT_MS` if network latency is high

### Import Errors
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Port Already in Use
```bash
# Find and kill process on port 8000
lsof -i :8000
kill -9 <PID>
```

## Integration with Other Services

### Reservas Service (SAGA Orchestrator)
- Calls `GET /api/v1/eventos/{evento_id}` to validate event exists and has capacity
- Expects RFC 7807 error format for 404/422/409 responses
- Propagates `X-Correlation-ID` for distributed tracing

### Usuarios Service
- No direct integration in MVP
- Future: Event organizer validation via Usuarios Service

## Monitoring & Observability

### Structured Logs
All logs output as JSON to stdout:
```json
{
  "timestamp": "2026-09-23T10:00:00.000Z",
  "level": "INFO",
  "service": "eventos-service",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "span_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Event created successfully",
  "context": {
    "evento_id": "550e8400-e29b-41d4-a716-446655440000",
    "operation": "create_event",
    "duration_ms": 45
  }
}
```

### Metrics (Future)
- Latency histograms per endpoint
- Error rate counters
- Throughput counters
- Health check status gauge