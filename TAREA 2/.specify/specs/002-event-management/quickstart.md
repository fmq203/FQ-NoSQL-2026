# Quickstart: Event Management (Eventos Service)

**Date**: 2026-09-20

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- MongoDB 7.0+, Redis 7.0+ (via Docker)

## Quick Start (Docker Compose)

```bash
cd /home/fqueirolo/TECNOLOGO/NoSQL/TAREA\ 2

# Levantar stack completo
docker compose up -d --build

# Verificar Eventos Service
docker compose ps eventos-service
# Up (healthy)

# Logs
docker compose logs -f eventos-service
```

## Verificar Endpoints

```bash
# Health check
curl http://localhost:8002/health
# {"status":"ok","service":"eventos"}

# Swagger UI
open http://localhost:8002/docs

# OpenAPI Spec
curl http://localhost:8002/openapi.json | jq .
```

## Probar Endpoints

### 1. Crear Evento (POST)
```bash
curl -X POST http://localhost:8002/api/eventos \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Concierto Rock 2026",
    "descripcion": "Gran festival de rock",
    "fecha": "2026-12-15T20:00:00Z",
    "ubicacion": {
      "venue": "Estadio Central",
      "direccion": "Av. Principal 123",
      "ciudad": "Madrid",
      "pais": "España",
      "coordenadas": {"lat": 40.4168, "lng": -3.7038}
    },
    "aforo_total": 50000,
    "precios": [
      {"categoria": "VIP", "precio": 200.0, "disponibles": 1000},
      {"categoria": "General", "precio": 80.0, "disponibles": 30000},
      {"categoria": "Popular", "precio": 40.0, "disponibles": 19000}
    ],
    "categorias": ["musica", "rock", "festival"]
  }'

# Response 201 con evento_id, entradas_disponibles=50000, estado=borrador
```

### 2. Obtener Evento (GET)
```bash
# Usar evento_id del paso anterior
curl http://localhost:8002/api/eventos/550e8400-e29b-41d4-a716-446655440001

# Response incluye entradas_disponibles actualizado
```

### 3. Verificar Inventario Redis (Interno)
```bash
# Conectar a Redis
docker compose exec redis redis-cli

# Ver inventario inicializado
GET inventario:550e8400-e29b-41d4-a716-446655440001
# "50000"

# Ver cache disponibilidad (tras GET evento)
GET evento:disp:550e8400-e29b-41d4-a716-446655440001
# "50000" (TTL 30s)
```

## Desarrollo Local

```bash
cd eventos-service

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Levantar MongoDB + Redis
docker compose up -d mongodb redis

uvicorn src.main:app --reload --port 8002
```

## Ejecutar Tests

```bash
pytest -v
pytest tests/contract/ -v
pytest tests/integration/ -v
```

## Variables de Entorno (.env)

```bash
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=eventflow
REDIS_URL=redis://localhost:6379
SERVICE_PORT=8002
```

## Estructura Clave

```
eventos-service/
├── src/
│   ├── main.py
│   ├── models/evento.py
│   ├── services/
│   │   ├── mongo.py
│   │   ├── redis_cache.py
│   │   └── evento_service.py
│   └── api/routes.py
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Troubleshooting

| Problema | Solución |
|----------|----------|
| Redis connection refused | `docker compose up -d redis` |
| Cache no invalida | Verificar `invalidar_cache_disponibilidad` llamado |
| Text search no funciona | Requiere MongoDB 4.4+, verificar índice creado |
| Inventario desincronizado | Verificar Lua script + renovación TTL 12h |

## Referencias

- Swagger: http://localhost:8002/docs
- `brain/microservices/eventos.md`
- `brain/data-models/event-schema.md`