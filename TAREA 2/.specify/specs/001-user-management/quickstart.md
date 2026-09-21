# Quickstart: User Management (Usuarios Service)

**Date**: 2026-09-20

## Prerequisites

- Docker + Docker Compose
- Python 3.11+ (para desarrollo local)
- MongoDB 7.0+ (via Docker)

## Quick Start (Docker Compose - Recommended)

```bash
# Desde raíz del repositorio
cd /home/fqueirolo/TECNOLOGO/NoSQL/TAREA\ 2

# Levantar todo el stack (MongoDB + 3 servicios)
docker compose up -d --build

# Verificar que Usuarios Service está healthy
docker compose ps usuarios-service
# Debe mostrar: Up (healthy)

# Ver logs
docker compose logs -f usuarios-service
```

## Verificar Endpoints

```bash
# Health check
curl http://localhost:8001/health
# {"status":"ok","service":"usuarios"}

# Swagger UI (documentación interactiva)
open http://localhost:8001/docs

# ReDoc (documentación alternativa)
open http://localhost:8001/redoc

# OpenAPI Spec (JSON)
curl http://localhost:8001/openapi.json | jq .
```

## Probar Endpoints Principales

### 1. Crear Usuario (POST)
```bash
curl -X POST http://localhost:8001/api/usuarios \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_documento": "DNI",
    "nro_documento": "12345678",
    "nombre": "Juan",
    "apellido": "Pérez",
    "email": "juan@example.com"
  }'

# Response 201:
# {
#   "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
#   "tipo_documento": "DNI",
#   "nro_documento": "12345678",
#   "nombre": "Juan",
#   "apellido": "Pérez",
#   "email": "juan@example.com",
#   "creado_en": "2026-09-20T10:00:00Z",
#   "historial_compras": []
# }
```

### 2. Obtener Usuario (GET)
```bash
# Usar usuario_id del paso anterior
curl http://localhost:8001/api/usuarios/550e8400-e29b-41d4-a716-446655440000
```

### 3. Listar Usuarios (GET con paginación)
```bash
# Primeros 10
curl "http://localhost:8001/api/usuarios?skip=0&limit=10"

# Siguientes 10
curl "http://localhost:8001/api/usuarios?skip=10&limit=10"
```

### 4. Exportar Anonimizado GDPR (GET)
```bash
# JSON (streaming)
curl http://localhost:8001/api/usuarios/exportar?format=json

# CSV
curl http://localhost:8001/api/usuarios/exportar?format=csv
```

## Desarrollo Local (Sin Docker)

```bash
cd usuarios-service

# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con MONGODB_URI=mongodb://localhost:27017

# Levantar solo MongoDB
docker compose up -d mongodb

# Ejecutar servicio
uvicorn src.main:app --reload --port 8001
```

## Ejecutar Tests

```bash
# Tests unitarios + integración (requiere MongoDB corriendo)
pytest -v

# Solo tests de contrato (OpenAPI)
pytest tests/contract/ -v

# Solo tests de integración
pytest tests/integration/ -v

# Con coverage
pytest --cov=src --cov-report=html
```

## Variables de Entorno (.env)

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=eventflow

# Servicio
SERVICE_PORT=8001

# GDPR Anonimización (CAMBIAR EN PRODUCCIÓN)
ANONYMIZATION_SALT=eventflow-salt-2026-change-in-production
```

## Estructura de Archivos Clave

```
usuarios-service/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── models/
│   │   └── usuario.py       # Pydantic models
│   ├── services/
│   │   ├── mongo.py         # MongoDB connection
│   │   └── usuario_service.py  # Business logic
│   ├── api/
│   │   └── routes.py        # Route handlers
│   └── utils/
│       └── anonymize.py     # GDPR hash function
├── tests/
│   ├── contract/
│   ├── integration/
│   └── unit/
├── Dockerfile
├── requirements.txt
├── .env.example
└── pytest.ini
```

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `email-validator not installed` | `pip install email-validator` |
| MongoDB connection refused | `docker compose up -d mongodb` y esperar healthy |
| DuplicateKeyError 409 | Email o documento ya existe, usar otro |
| Exportación vacía | Verificar que hay usuarios en BD |
| Health check fails | Verificar que `curl` está en Dockerfile |

## Referencias

- `brain/microservices/usuarios.md` - Spec completa
- `brain/data-models/user-schema.md` - Modelo de datos
- `brain/endpoints/usuarios-endpoints.md` - API reference
- Swagger UI: http://localhost:8001/docs