# Quickstart: Reservation & Payment (Reservas Service)

**Date**: 2026-09-20

## Prerequisites

- Docker + Docker Compose (stack completo requerido)
- Python 3.11+
- Stack: MongoDB + Redis + PostgreSQL + Usuarios (8001) + Eventos (8002)

## Quick Start (Docker Compose - Requerido)

```bash
cd /home/fqueirolo/TECNOLOGO/NoSQL/TAREA\ 2

# Levantar TODO el stack (6 contenedores)
docker compose up -d --build

# Verificar todos healthy
docker compose ps
# Debe mostrar 6 contenedores Up (healthy)

# Ver logs Reservas Service
docker compose logs -f reservas-service
```

## Verificar Endpoints

```bash
# Health check
curl http://localhost:8003/health
# {"status":"ok","service":"reservas"}

# Swagger UI
open http://localhost:8003/docs

# OpenAPI Spec
curl http://localhost:8003/openapi.json | jq .
```

## Probar SAGA Completa (Happy Path)

### 1. Crear Usuario (prerrequisito)
```bash
curl -X POST http://localhost:8001/api/usuarios \
  -H "Content-Type: application/json" \
  -d '{"tipo_documento":"DNI","nro_documento":"12345678","nombre":"Juan","apellido":"Pérez","email":"juan@example.com"}'
# Guardar usuario_id del response
```

### 2. Crear Evento con aforo (prerrequisito)
```bash
curl -X POST http://localhost:8002/api/eventos \
  -H "Content-Type: application/json" \
  -d '{
    "nombre":"Test Event","descripcion":"Evento prueba","fecha":"2026-12-31T20:00:00Z",
    "ubicacion":{"venue":"Test Venue","ciudad":"Test City","pais":"Test"},
    "aforo_total":100,
    "precios":[{"categoria":"General","precio":50.0,"disponibles":100}],
    "categorias":["test"]
  }'
# Guardar evento_id del response
```

### 3. Ejecutar Reserva (SAGA)
```bash
# Usar usuario_id y evento_id de arriba
curl -X POST http://localhost:8003/api/reservar \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id":"<USUARIO_ID>",
    "evento_id":"<EVENTO_ID>",
    "cantidad":2,
    "metodo_pago":"tarjeta"
  }'

# Response 201 esperado:
# {
#   "reserva_id": "550e8400-e29b-41d4-a716-446655440002",
#   "estado": "confirmada",
#   "numero_confirmacion": "CONF-20260920-A1B2C3D4"
# }
```

## Verificar Persistencia Multi-DB

### MongoDB: Reserva + saga_log
```bash
docker compose exec mongodb mongosh eventflow --eval 'db.reservas.find().pretty()'
```

### Redis: Pago + Inventario
```bash
docker compose exec redis redis-cli

# Ver pago creado
HGETALL pago:<RESERVA_ID>

# Ver inventario decrementado
GET inventario:<EVENTO_ID>
# Debe ser 98 (100 - 2)
```

### PostgreSQL: Event Log (Event Sourcing)
```bash
docker compose exec postgresql psql -U eventflow_user -d eventflow -c "
SELECT event_type, aggregate_id, timestamp, payload 
FROM event_log 
WHERE aggregate_id = '<RESERVA_ID>' 
ORDER BY timestamp;
"

# Debe mostrar 7 eventos ordenados:
# SAGA_STARTED, USUARIO_VALIDADO, EVENTO_VALIDADO, 
# PAGO_PROCESADO, INVENTARIO_DECREMENTADO, 
# RESERVA_CONFIRMADA, SAGA_COMPLETED
```

## Probar Compensaciones (Fallo Simulado)

### Opción A: Fallo MongoDB (detener MongoDB tras pago)
```bash
# 1. Detener MongoDB
docker compose stop mongodb

# 2. Intentar reserva (fallará en Paso 5)
curl -X POST http://localhost:8003/api/reservar ...

# 3. Verificar compensación Redis ejecutada
docker compose exec redis redis-cli
GET inventario:<EVENTO_ID>
# Debe ser 100 (rollback INCRBY)
HGETALL pago:<RESERVA_ID>
# Debe ser vacío (DEL ejecutado)

# 4. Reactivar MongoDB
docker compose start mongodb
```

### Opción B: Inventario Insuficiente (409)
```bash
# Reservar más de lo disponible
curl -X POST http://localhost:8003/api/reservar \
  -d '{"usuario_id":"...","evento_id":"...","cantidad":200,"metodo_pago":"tarjeta"}'

# Response 409: "Inventario insuficiente. Disponibles: 98"
```

### Opción C: Usuario/Evento No Existe (404)
```bash
curl -X POST http://localhost:8003/api/reservar \
  -d '{"usuario_id":"00000000-0000-0000-0000-000000000000","evento_id":"...","cantidad":1,"metodo_pago":"tarjeta"}'
# 404 "Usuario no encontrado"
```

## Desarrollo Local

```bash
cd reservas-service

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Requiere stack completo corriendo (docker compose up -d)
uvicorn src.main:app --reload --port 8003
```

## Ejecutar Tests

```bash
# Requiere stack completo (docker compose up -d)
pytest -v

# Tests específicos
pytest tests/integration/test_saga_happy_path.py -v
pytest tests/integration/test_saga_compensations.py -v
pytest tests/unit/test_lua_scripts.py -v
pytest tests/unit/test_handlers.py -v
```

## Variables de Entorno (.env)

```bash
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=eventflow
REDIS_URL=redis://localhost:6379
POSTGRESQL_URI=postgresql://eventflow_user:eventflow_password@localhost:5432/eventflow
USUARIOS_SERVICE_URL=http://localhost:8001
EVENTOS_SERVICE_URL=http://localhost:8002
SERVICE_PORT=8003
```

## Estructura Clave

```
reservas-service/
├── src/
│   ├── main.py
│   ├── chain/
│   │   ├── handler.py       # Base Handler + ReservaContext
│   │   ├── validators.py    # 6 handlers
│   │   └── builder.py       # ChainBuilder
│   ├── services/
│   │   ├── mongo.py
│   │   ├── redis_pago.py    # Lua scripts registrados
│   │   ├── postgresql.py    # AsyncPG pool
│   │   ├── http_clients.py  # httpx clients
│   │   └── saga_orchestrator.py
│   ├── api/routes.py
│   └── utils/idempotency.py
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Troubleshooting

| Problema | Solución |
|----------|----------|
| Connection refused Usuarios/Eventos | Verificar `docker compose ps` - ambos healthy |
| Lua script not found | Verificar registro en `redis_pago.py` startup |
| PG connection failed | Verificar PostgreSQL healthy, credenciales en .env |
| Idempotencia falla | Verificar unique index `numero_confirmacion` en MongoDB |
| Compensación no ejecuta | Logs: buscar "COMPENSACION_EJECUTADA" en PostgreSQL |

## Referencias

- Swagger: http://localhost:8003/docs
- `brain/microservices/reservas-pagos.md`
- `brain/architecture/saga-flow.md`
- `brain/architecture/chain-of-responsibility.md`
- `brain/data-models/reservation-schema.md`