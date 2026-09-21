# Implementation Plan: Event Management (Eventos Service)

**Branch**: `002-event-management` | **Date**: 2026-09-20 | **Spec**: .specify/specs/002-event-management/spec.md

## Summary

Implementar **Eventos Service** (FastAPI + MongoDB + Redis cache) con 2 endpoints REST, modelo de datos con precios/ubicación embebidos, sincronización inventario Redis para SAGA, y consistencia eventual para lecturas.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: 
- FastAPI 0.104.0, Uvicorn 0.24.0
- Pydantic 2.x, PyMongo 4.5.0
- Redis 5.0.0 (async redis-py)
- python-dotenv

**Storage**: 
- MongoDB 7.0 (colección `eventos`, réplica set)
- Redis 7.0 (cache disponibilidad TTL 30s, contador inventario)

**Testing**: pytest, pytest-asyncio, httpx.AsyncClient, fakeredis para tests

**Target Platform**: Linux container (Docker), puerto 8002

**Performance Goals**: 
- Crear evento: < 150ms p95
- Obtener evento: < 50ms p95 (secondaryPreferred), < 10ms cache hit
- Cache hit rate: > 90%

**Constraints**: 
- Consistencia eventual lecturas (secondaryPreferred)
- Sincronización eventual Redis ↔ MongoDB (< 500ms)
- Índices: fecha, estado+fecha, text search
- Embedded: ubicacion, precios[], categorias[]

## Constitution Check

- ✅ Microservice Autonomy: Own MongoDB, Redis cache local
- ✅ API-First: OpenAPI auto-generated, versioning strategy defined
- ✅ Test-First: Contract + integration tests
- ✅ Observability: /health, logging, metrics, tracing
- ✅ Polyglot Persistence: MongoDB (documentos) + Redis (cache/contadores)
- ✅ Security/Privacy: No PII, secrets in env, RFC 7807 errors
- ✅ Simplicity: No auth, cache-aside pattern
- ✅ Distributed Transactions: SAGA compensation for inventory

## Requirements Traceability

| Spec Requirement | Plan Section | Tasks |
|------------------|--------------|-------|
| EM-FR-001 | Phase 3 (US1) | T017-T020 |
| EM-FR-002 | Phase 3 (US1) | T019 |
| EM-FR-003 | Phase 4 (US2) | T025-T027 |
| EM-FR-004 | Phase 3/5 | T018, T040-T043 |
| EM-FR-005 | Phase 4/5 | T012, T041 |
| EM-FR-006 | Phase 5 | T044 |
| EM-FR-007 | Phase 2 | T011, T051 |
| EM-SC-001 | Performance Goals | T016 |
| EM-SC-002 | Performance Goals | T023, T024 |
| EM-SC-003 | Performance Goals | T037 |
| EM-SC-004 | Performance Goals | T024, T050 |
| EM-SC-005 | Phase 5 | T038 |
| EM-SC-006 | Phase 2 | T011, T051 |

## Project Structure

```
eventos-service/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── evento.py          # Pydantic: Evento, EventoCreate, PrecioCategoria
│   │   └── enums.py           # EstadoEvento enum
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mongo.py           # MongoDB connection + indexes
│   │   ├── redis_cache.py     # Redis cache + inventario sync
│   │   └── evento_service.py  # Business logic
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── middleware.py      # RFC 7807, versioning, tracing
│   └── utils/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── contract/
│   │   ├── __init__.py
│   │   └── test_eventos_openapi.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_eventos_flow.py
│   │   ├── test_inventory_consistency.py
│   │   └── test_text_search.py
│   ├── performance/
│   │   ├── __init__.py
│   │   ├── test_create_event.py
│   │   ├── test_get_event.py
│   │   ├── test_cache_hit_rate.py
│   │   └── test_redis_sync.py
│   └── unit/
│       ├── __init__.py
│       └── test_redis_sync.py
└── pytest.ini
```

## Phase 1: Design

### Data Model (MongoDB)

Ver `brain/data-models/event-schema.md`.

**Colección**: `eventos`

**Índices**:
```javascript
db.eventos.createIndex({ "fecha": 1 })
db.eventos.createIndex({ "estado": 1, "fecha": 1 })
db.eventos.createIndex({ "nombre": "text", "descripcion": "text", "categorias": "text" })
db.eventos.createIndex({ "entradas_disponibles": 1 })
```

**Documento**:
```json
{
  "_id": "UUID",
  "nombre": "string",
  "descripcion": "string",
  "fecha": "ISODate",
  "ubicacion": { "venue": "", "direccion": "", "ciudad": "", "pais": "", "coordenadas": { "lat": 0, "lng": 0 } },
  "aforo_total": 50000,
  "entradas_disponibles": 48500,
  "precios": [ { "categoria": "VIP", "precio": 200.0, "disponibles": 950 } ],
  "categorias": ["musica", "rock"],
  "estado": "publicado",
  "creado_en": "ISODate",
  "actualizado_en": "ISODate"
}
```

### Redis Keys

| Key | Tipo | TTL | Descripción |
|-----|------|-----|-------------|
| `inventario:{evento_id}` | String | 86400 (renovado) | Contador entradas disponibles |
| `evento:disp:{evento_id}` | String | 30 | Cache disponibilidad para lecturas |

### Contracts (OpenAPI)

Auto-generado en `/openapi.json`. Endpoints:
- POST `/api/v1/eventos` - Crear evento
- GET `/api/v1/eventos/{evento_id}` - Obtener con aforo disponible
- GET `/api/v1/eventos?search={query}` - Búsqueda full-text

### Quickstart

```bash
cd eventos-service
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn src.main:app --reload --port 8002

# Tests
pytest -v

# Docker
docker compose up -d eventos-service mongodb redis
curl http://localhost:8002/health
curl http://localhost:8002/docs
```