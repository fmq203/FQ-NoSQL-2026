# Implementation Plan: User Management (Usuarios Service)

**Branch**: `001-user-management` | **Date**: 2026-09-20 | **Spec**: .specify/specs/001-user-management/spec.md

**Input**: Feature specification from `.specify/specs/001-user-management/spec.md`

## Summary

Implementar **Usuarios Service** (FastAPI + MongoDB) con 4 endpoints REST, modelo de datos con historial embebido, exportación GDPR anonimizada, y consistencia eventual para lecturas.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: 
- FastAPI 0.104.0, Uvicorn 0.24.0
- Pydantic 2.x (con email-validator)
- PyMongo 4.5.0 (async Motor preferred)
- python-dotenv, httpx

**Storage**: MongoDB 7.0 (colección `usuarios`, réplica set para secondaryPreferred)

**Testing**: pytest 7.4, pytest-asyncio, httpx.AsyncClient para contract tests

**Target Platform**: Linux container (Docker), puerto 8001

**Project Type**: Microservicio web API

**Performance Goals**: 
- Crear usuario: < 100ms p95
- Obtener usuario: < 50ms p95 (secondaryPreferred)
- Listar paginado: < 200ms
- Exportar 10k usuarios: < 2s streaming

**Constraints**: 
- Consistencia eventual en lecturas (read preference secondaryPreferred)
- Consistencia fuerte en escrituras (write concern majority + journal)
- Índices únicos: email, nro_documento
- Embedded historial_compras[] máx 50 items ($slice)

**Scale/Scope**: 
- 100k+ usuarios
- 50 compras/usuario promedio
- Exportación batch streaming

## Constitution Check

- ✅ Microservice Autonomy: Own DB, no shared storage
- ✅ API-First: OpenAPI auto-generated from FastAPI
- ✅ Test-First: Contract tests before implementation
- ✅ Observability: /health, structured logging, metrics
- ✅ Polyglot Persistence: MongoDB justified (embedded history)
- ✅ Security/Privacy: GDPR anonymization endpoint
- ✅ Simplicity: No auth, no frameworks beyond FastAPI

## Requirements Traceability

| Spec Requirement | Plan Section | Tasks |
|------------------|--------------|-------|
| UM-FR-001 | Phase 3 (US1) | T019-T023 |
| UM-FR-002 | Phase 4 (US2) | T027-T029 |
| UM-FR-003 | Phase 5 (US3) | T033-T035 |
| UM-FR-004 | Phase 6 (US4) | T044-T048 |
| UM-FR-005 | Phase 6 (US4) | T044-T048 |
| UM-FR-006 | Phase 6 (US4) | T044-T048 |
| UM-FR-007 | Phase 2 | T011, T011b, T011c |
| UM-SC-001 | Performance Goals | T016 |
| UM-SC-002 | Performance Goals | T026 |
| UM-SC-003 | Performance Goals | T032 |
| UM-SC-004 | Performance Goals | T039 |
| UM-SC-005 | Phase 6 | T040, T041 |
| UM-SC-006 | Phase 6 | T015, T038, T042 |
| UM-SC-007 | Phase 2 | T011 |

## Project Structure

### Documentation (this feature)
```
.specify/specs/001-user-management/
├── spec.md              # This feature specification
├── plan.md              # This file
├── research.md          # Phase 0: Technical decisions
├── data-model.md        # Phase 1: MongoDB schema
├── quickstart.md        # Phase 1: Run/test instructions
├── contracts/           # Phase 1: OpenAPI references
│   └── openapi.json     # Auto-generated from running service
└── tasks.md             # Phase 2: Implementation tasks
```

### Source Code (repository root)
```
usuarios-service/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── usuario.py       # Pydantic models (Usuario, UsuarioCreate, Export)
│   │   └── enums.py         # TipoDocumento enum
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mongo.py         # MongoDB connection + indexes
│   │   └── usuario_service.py  # Business logic
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py        # Route handlers
│   │   └── middleware.py    # RFC 7807 error formatting
│   └── utils/
│       ├── __init__.py
│       └── anonymize.py     # GDPR hash function
├── tests/
│   ├── __init__.py
│   ├── contract/
│   │   ├── __init__.py
│   │   ├── test_usuarios_openapi.py
│   │   └── test_logging_schema.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_usuarios_flow.py
│   │   ├── test_export_integrity.py
│   │   └── test_tracing.py
│   ├── performance/
│   │   ├── __init__.py
│   │   ├── test_create_user.py
│   │   ├── test_get_user.py
│   │   ├── test_list_users.py
│   │   └── test_export_users.py
│   └── unit/
│       ├── __init__.py
│       └── test_anonymize.py
├── docs/
│   └── anonymization-salt-rotation.md
└── pytest.ini
```

**Structure Decision**: Single project per microservice. Clean architecture: models → services → api/routes. Tests mirror structure.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Embedded historial_compras | Atomicidad usuario+historial, single query | Separate collection requiere JOIN/$lookup, rompe atomicidad |
| Exportación streaming | Memoria acotada para 100k+ usuarios | Cargar todo en RAM causa OOM |

## Phase 0: Research (Completed)

Key decisions documented in:
- `brain/decisions/db-selection.md` — MongoDB para usuarios
- `brain/decisions/consistency-strategy.md` — Eventual reads, strong writes
- `brain/data-models/user-schema.md` — Schema detallado + índices
- `brain/data-models/db-choice-rationale.md` — Justificación embedded vs reference
- `brain/microservices/usuarios.md` — Spec completa servicio

## Phase 1: Design (Data Model, Contracts, Quickstart)

### Data Model (MongoDB)

Ver `brain/data-models/user-schema.md` para schema completo.

**Colección**: `usuarios`

**Índices**:
```javascript
db.usuarios.createIndex({ "email": 1 }, { unique: true })
db.usuarios.createIndex({ "nro_documento": 1 }, { unique: true })
db.usuarios.createIndex({ "creado_en": -1 })
db.usuarios.createIndex({ "historial_compras.fecha_compra": -1 })
```

**Documento**:
```json
{
  "_id": "UUID",
  "tipo_documento": "DNI|Pasaporte",
  "nro_documento": "string",
  "nombre": "string",
  "apellido": "string",
  "email": "string",
  "creado_en": "ISODate",
  "historial_compras": [
    { "reserva_id": "UUID", "evento_id": "UUID", "cantidad": 2, "precio_total": 160.0, "fecha_compra": "ISODate", "estado": "confirmada" }
  ]
}
```

### Contracts (OpenAPI)

Auto-generado por FastAPI en `/openapi.json` y `/docs`. Referencia:
- `brain/endpoints/usuarios-endpoints.md` (por crear)
- Endpoints: POST /api/usuarios, GET /api/usuarios, GET /api/usuarios/{id}, GET /api/usuarios/exportar

### Quickstart

```bash
# Desarrollo local
cd usuarios-service
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configurar MONGODB_URI
uvicorn src.main:app --reload --port 8001

# Tests
pytest -v

# Docker
docker compose up -d usuarios-service mongodb
curl http://localhost:8001/health
curl http://localhost:8001/docs
```