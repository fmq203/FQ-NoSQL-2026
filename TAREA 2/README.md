# EventFlow — Sistema de Microservicios para Gestión de Eventos

**Tarea 2 NoSQL** — Diseño e implementación de un sistema de microservicios con bases de datos políglotas, patrones de consistencia distribuida y cumplimiento GDPR.

---

## 📋 Descripción del Proyecto

**EventFlow** es una plataforma ficticia de gestión y venta de entradas para eventos. El sistema implementa una arquitectura de microservicios diseñada para alto volumen de transacciones y consultas, aplicando:

- **3 Bases de Datos NoSQL** (especialización por caso de uso)
- **Patrón SAGA con Orquestación** (transacciones distribuidas)
- **Patrón Chain of Responsibility** (validaciones secuenciales)
- **Event Sourcing + CQRS** (auditoría inmutable)
- **Anonimización GDPR** (exportación masiva irreversible)

---

## 🏗️ Arquitectura

### Vista General

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EVENTFLOW ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   CLIENT    │    │  USUARIOS   │    │  EVENTOS    │    │  RESERVAS   │  │
│  │  (Browser,  │◄──►│  SERVICE    │    │  SERVICE    │    │  SERVICE    │  │
│  │   Postman,  │    │  :8001      │    │  :8002      │    │  :8003      │  │
│  │   JMeter)   │    │             │    │             │    │ (Orquestador)│  │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│                            │                   │                   │          │
│              ┌─────────────┼───────────────────┼───────────────────┼────────┐ │
│              ▼             ▼                   ▼                   ▼        │ │
│       ┌─────────────┐ ┌─────────────┐   ┌─────────────┐      ┌─────────────┐│
│       │  MONGODB    │ │   REDIS     │   │  REDIS      │      │ POSTGRESQL  ││
│       │  :27017     │ │  :6379      │   │  :6379      │      │  :5432      ││
│       ├─────────────┤ ├─────────────┤   ├─────────────┤      ├─────────────┤│
│       │ • Usuarios  │ │ • Pagos     │   │ • Inventario│      │ • Event Log ││
│       │ • Eventos   │ │   (Lua      │   │   (Contador)│      │   (Audit)   ││
│       │ • Reservas  │ │   atomic)   │   │ • Cache     │      │ • CQRS      ││
│       │ • Historial │ │ • TTL 24h   │   │   disponib. │      │ • GDPR      ││
│       └─────────────┘ └─────────────┘   └─────────────┘      └─────────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Microservicios

| Servicio | Puerto | Responsabilidad | Bases de Datos |
|----------|--------|-----------------|----------------|
| **Usuarios** | 8001 | Perfiles, historial compras, exportación GDPR | MongoDB |
| **Eventos** | 8002 | Catálogo, aforo, disponibilidad | MongoDB + Redis (cache) |
| **Reservas y Pagos** | 8003 | Orquestador SAGA, Chain of Responsibility, pagos | Redis + MongoDB + PostgreSQL |

### Bases de Datos (Políglota)

| DB | Tipo | Uso | Justificación |
|----|------|-----|---------------|
| **MongoDB** | Documental | Usuarios, Eventos, Reservas | Embedded history, esquema flexible, sharding |
| **Redis** | Clave-Valor (In-memory) | Pagos atómicos, inventario, cache | Lua scripts atómicos, sub-ms latency |
| **PostgreSQL** | Relacional | Audit log, Event Sourcing | ACID, CQRS, compliance, particionado |

---

## 🔄 Flujo SAGA — Compra de Entradas

El **Servicio de Reservas** actúa como **Orquestador Central**:

```mermaid
sequenceDiagram
    participant Client
    participant RS as Reservas<br/>(Orquestador)
    participant US as Usuarios<br/>Service
    participant ES as Eventos<br/>Service
    participant Redis
    participant MongoDB
    participant PG as PostgreSQL

    Client->>RS: POST /api/reservar
    Note over RS: Chain of Responsibility
    RS->>US: GET /api/usuarios/{id}
    US-->>RS: 200 OK / 404
    RS->>ES: GET /api/eventos/{id}
    ES-->>RS: 200 OK {aforo} / 404
    Note over RS,Redis: Lua Script Atómico
    RS->>Redis: EVAL pagar_y_decrementar.lua
    Redis-->>RS: {pago_ok, inventario_ok}
    alt Éxito
        RS->>MongoDB: INSERT reserva
        RS->>PG: INSERT audit_event (SAGA_COMPLETED)
        RS-->>Client: 201 Reserva confirmada
    else Fallo
        RS->>Redis: COMPENSACIÓN (rollback)
        RS->>PG: INSERT audit_event (SAGA_FAILED)
        RS-->>Client: 400/409/500
    end
```

### 6 Pasos SAGA + Compensaciones

| Paso | Handler | Acción | Consistencia | Compensación si falla |
|------|---------|--------|--------------|----------------------|
| 1 | ValidadorDeDatos | Validar UUIDs, cantidad>0, método pago | Local | Ninguna |
| 2 | ValidadorInventario | GET Usuarios Service | Eventual | Ninguna |
| 3 | ValidadorEvento | GET Eventos Service + aforo | Eventual | Ninguna |
| 4 | **ProcesadorPago** | **Redis Lua: Pago + DECRBY inventario** | **Fuerte (Atómico)** | Rollback interno Lua |
| 5 | ConfirmadorReserva | INSERT MongoDB reserva | **Fuerte (Majority)** | DELETE reserva + Lua INCRBY+DEL |
| 6 | Auditor | INSERT PostgreSQL event_log | **Fuerte (ACID)** | Log WARNING only |

### Atomicidad Crítica: Redis Lua Script (Paso 4)

```lua
-- KEYS[1] = inventario:evento_id, KEYS[2] = pago:reserva_id
-- ARGV[1]=cantidad, ARGV[2]=reserva_id, ARGV[3]=usuario_id, ARGV[4]=monto, ARGV[5]=metodo_pago

local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
if disponible < tonumber(ARGV[1]) then
    return {0, 'INVENTARIO_INSUFICIENTE'}
end

-- TRANSACCIÓN ATÓMICA: Verificar + Decrementar + Registrar
redis.call('DECRBY', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2], 
    'reserva_id', ARGV[2], 'usuario_id', ARGV[3],
    'monto', ARGV[4], 'metodo_pago', ARGV[5],
    'estado', 'confirmado', 'timestamp', os.date('!%Y-%m-%dT%H:%M:%SZ')
)
redis.call('EXPIRE', KEYS[2], 86400)
return {1, 'OK'}
```

---

## ⛓️ Chain of Responsibility — Validaciones Secuenciales

El **Servicio de Reservas** estructura la lógica con 6 handlers encadenados:

```mermaid
flowchart TD
    Request[POST /api/reservar] --> H1[ValidadorDeDatos]
    H1 -->|OK| H2[ValidadorInventario]
    H1 -->|Error| Resp400[400 Bad Request]
    H2 -->|OK| H3[ValidadorEvento]
    H2 -->|No existe| Resp404U[404 Usuario]
    H3 -->|OK + Aforo| H4[ProcesadorPago]
    H3 -->|No existe| Resp404E[404 Evento]
    H3 -->|Sin aforo| Resp409[409 Inventario]
    H4 -->|Pago OK| H5[ConfirmadorReserva]
    H4 -->|Falla| Resp500[500 Pago]
    H5 -->|Reserva OK| H6[Auditor]
    H5 -->|Mongo falla| Comp[Compensación Rollback]
    H6 -->|Audit OK| Resp201[201 Confirmada]
    H6 -->|Audit falla| Resp201W[201 + Warning]
    Comp --> Resp500C[500 + Rollback]
```

### Handlers

| Orden | Handler | Responsabilidad | Dependencia |
|-------|---------|-----------------|-------------|
| 1 | `ValidadorDeDatos` | Validar UUIDs, cantidad>0, método pago enum | Local |
| 2 | `ValidadorInventario` | GET `/api/usuarios/{id}` | Usuarios Service (HTTP) |
| 3 | `ValidadorEvento` | GET `/api/eventos/{id}` + aforo | Eventos Service (HTTP) |
| 4 | `ProcesadorPago` | Redis Lua: Pago + DECRBY inventario | Redis (Lua atómico) |
| 5 | `ConfirmadorReserva` | INSERT MongoDB reserva + saga_log | MongoDB |
| 6 | `Auditor` | INSERT PostgreSQL event_log | PostgreSQL |

### Ventajas
- **Separación de responsabilidades** (SRP)
- **Testabilidad** unitaria por handler
- **Extensibilidad**: agregar validación = nuevo handler
- **Compensación natural**: Fallo en N → compensar N-1...4

---

## 🔐 Anonimización GDPR — Exportación Masiva

**Endpoint**: `GET /api/usuarios/exportar?format=json|csv`

### Algoritmo: Hash Irreversible SHA-256 + Salt

```python
import hashlib
import os

SALT = os.getenv("ANONYMIZATION_SALT", "eventflow-salt-2026")

def anonimizar_usuario(usuario):
    usuario_hash = hashlib.sha256(
        f"{usuario.usuario_id}{SALT}".encode()
    ).hexdigest()
    
    return {
        "usuario_hash": usuario_hash,
        "eventos_comprados": len(usuario.historial_compras),
        "gasto_total": round(sum(c.precio_total for c in usuario.historial_compras), 2)
    }
```

### Propiedades Garantizadas

| Propiedad | Implementación |
|-----------|----------------|
| **Irreversible** | SHA-256 one-way function |
| **Determinista** | Mismo usuario = mismo hash (deduplicación analítica) |
| **Anti-rainbow** | Salt único por despliegue (`ANONYMIZATION_SALT`) |
| **Preserva analítica** | `eventos_comprados` (count), `gasto_total` (sum) |

### Datos Eliminados vs Preservados

| Eliminados (PII) | Preservados (Análisis) |
|------------------|------------------------|
| nombre, apellido | eventos_comprados |
| email | gasto_total |
| tipo_documento, nro_documento | — |

---

## 📚 Documentación Completa (Brain)

```
brain/
├── CLAUDE.md                 # Mapa principal + protocolos
├── index.md                  # Catálogo de archivos
├── decisions/                # Decisiones arquitectónicas
│   ├── db-selection.md       # Por qué 3 DBs + justificación
│   ├── consistency-strategy.md  # Eventual vs Fuerte por operación
│   └── deployment-strategy.md   # Docker → K8s
├── architecture/             # Diagramas y overview
│   ├── overview.md
│   ├── microservices-diagram.md
│   ├── data-flow.md
│   ├── saga-flow.md          # Diagrama completo SAGA
│   └── chain-of-responsibility.md
├── patterns/                 # Patrones implementados
│   ├── saga-pattern.md       # SAGA Orchestration
│   ├── chain-of-responsibility.md  # 6 handlers
│   └── event-sourcing-cqrs.md      # Event Sourcing + CQRS
├── data-models/              # Schemas por DB
│   ├── user-schema.md
│   ├── event-schema.md
│   ├── reservation-schema.md
│   └── db-choice-rationale.md
├── endpoints/                # Referencias OpenAPI
│   ├── usuarios-endpoints.md
│   ├── eventos-endpoints.md
│   └── reservas-endpoints.md
├── deployment/               # Docker + K8s
│   ├── docker-setup.md
│   ├── docker-compose.md
│   └── deployment-checklist.md
└── learnings/                # Registro de decisiones técnicas
```

---

## 🚀 Quick Start

### Requisitos
- Python 3.11+
- Docker & Docker Compose
- Git

### Opción A: Docker Compose (Recomendado)

```bash
# 1. Clonar y entrar
git clone <repo>
cd "NoSQL/TAREA 2"

# 2. Construir y levantar TODO
docker compose up -d --build

# 3. Verificar estado
docker compose ps
# Debe mostrar 6 contenedores: Up (healthy)

# 4. Probar endpoints
curl http://localhost:8001/health  # {"status":"ok","service":"usuarios"}
curl http://localhost:8002/health  # {"status":"ok","service":"eventos"}
curl http://localhost:8003/health  # {"status":"ok","service":"reservas"}

# 5. Swagger UI
open http://localhost:8001/docs  # Usuarios
open http://localhost:8002/docs  # Eventos
open http://localhost:8003/docs  # Reservas
```

### Opción B: Desarrollo Local

```bash
# 1. Virtual env
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Levantar solo BDs
docker compose up -d mongodb redis postgresql

# 3. Configurar .env
cp .env.example .env

# 4. Ejecutar servicios (terminales separadas)
cd usuarios-service && uvicorn src.main:app --reload --port 8001
cd eventos-service && uvicorn src.main:app --reload --port 8002
cd reservas-service && uvicorn src.main:app --reload --port 8003
```

---

## 🧪 Testing

### Con Swagger UI
```bash
http://localhost:8001/docs  → Usuarios
http://localhost:8002/docs  → Eventos
http://localhost:8003/docs  → Reservas
```

### Con cURL (Flujo Completo)

```bash
# 1. Crear usuario
USER=$(curl -s -X POST http://localhost:8001/api/usuarios \
  -H "Content-Type: application/json" \
  -d '{"tipo_documento":"DNI","nro_documento":"12345678","nombre":"Juan","apellido":"Pérez","email":"juan@example.com"}')
USER_ID=$(echo $USER | jq -r .usuario_id)

# 2. Crear evento con aforo
EVENT=$(curl -s -X POST http://localhost:8002/api/eventos \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Test Event","fecha":"2026-12-31T20:00:00Z","ubicacion":{"venue":"Test","ciudad":"City","pais":"Country"},"aforo_total":100,"precios":[{"categoria":"General","precio":50,"disponibles":100}],"categorias":["test"]}')
EVENT_ID=$(echo $EVENT | jq -r .evento_id)

# 3. Ejecutar reserva (SAGA completa)
curl -X POST http://localhost:8003/api/reservar \
  -H "Content-Type: application/json" \
  -d "{\"usuario_id\":\"$USER_ID\",\"evento_id\":\"$EVENT_ID\",\"cantidad\":2,\"metodo_pago\":\"tarjeta\"}"

# 4. Verificar en todas las BDs
docker compose exec mongodb mongosh eventflow --eval 'db.reservas.find().pretty()'
docker compose exec redis redis-cli HGETALL pago:$(echo $RESERVA | jq -r .reserva_id)
docker compose exec postgresql psql -U eventflow_user -d eventflow -c "SELECT * FROM event_log ORDER BY timestamp DESC LIMIT 10"
```

### Tests Automatizados

```bash
# Instalar deps
pip install pytest pytest-asyncio pytest-cov fakeredis

# Tests unitarios + integración
pytest -v

# Coverage
pytest --cov=src --cov-report=html
```

---

## 📁 Estructura del Proyecto

```
.
├── brain/                      # Documentación arquitectónica (Second Brain)
│   ├── CLAUDE.md              # Protocolo + mapa
│   ├── decisions/             # 3 decisiones clave
│   ├── architecture/          # 5 diagramas
│   ├── patterns/              # 3 patrones documentados
│   ├── data-models/           # 4 schemas + rationale
│   ├── endpoints/             # 3 referencias OpenAPI
│   ├── deployment/            # 3 archivos Docker/K8s
│   └── learnings/             # Registro técnico append-only
│
├── usuarios-service/          # Puerto 8001
│   ├── src/
│   │   ├── main.py           # FastAPI app
│   │   ├── models/           # Pydantic models
│   │   ├── services/         # MongoDB, lógica
│   │   ├── api/routes.py     # Endpoints
│   │   └── utils/anonymize.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── eventos-service/           # Puerto 8002
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── reservas-service/          # Puerto 8003 (Orquestador)
│   ├── src/
│   │   ├── chain/            # Chain of Responsibility
│   │   │   ├── handler.py
│   │   │   ├── validators.py
│   │   │   └── builder.py
│   │   ├── services/         # MongoDB, Redis, PG, HTTP clients
│   │   └── api/routes.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── .specify/                  # Spec-kit para Spec-Driven Development
│   ├── specs/
│   │   ├── 001-user-management/
│   │   ├── 002-event-management/
│   │   └── 003-reservation-payment/
│   └── memory/constitution.md
│
├── .github/workflows/         # CI/CD (GitHub Actions)
├── docker-compose.yml         # Stack completo
├── requirements.txt           # Deps base
├── .env.example
└── README.md
```

---

## 🔧 Variables de Entorno

Ver `.env.example`. Configuración clave:

```bash
# Usuarios
MONGODB_URI=mongodb://localhost:27017
ANONYMIZATION_SALT=eventflow-salt-2026-change-in-production

# Eventos
REDIS_URL=redis://localhost:6379

# Reservas
POSTGRESQL_URI=postgresql://user:pass@localhost:5432/eventflow
USUARIOS_SERVICE_URL=http://localhost:8001
EVENTOS_SERVICE_URL=http://localhost:8002
```

---

## 🚢 Despliegue

### Local (Docker Compose)
```bash
docker compose up -d --build
```

### Kubernetes (Producción - Preparado)
```bash
# HPA, Ingress TLS, Network Policies, Secrets (Vault), mTLS (Istio)
# Ver brain/deployment/deployment-checklist.md
```

---

## 📅 Fechas de Entrega

| Hito | Fecha |
|------|-------|
| **Pre-defensa** | Jueves 5 de noviembre 2026 |
| **Defensa Final** | Jueves 12 de noviembre 2026 |
| **Presentación** | ~12 min (demo + arquitectura + opcional slides) |

---

## 👥 Equipo

> Agregar nombres e integrantes del grupo

---

## 📖 Referencias Técnicas

- **SAGA Pattern**: `brain/patterns/saga-pattern.md`
- **Chain of Responsibility**: `brain/patterns/chain-of-responsibility.md`
- **Event Sourcing + CQRS**: `brain/patterns/event-sourcing-cqrs.md`
- **3 DBs Justificación**: `brain/decisions/db-selection.md`
- **Consistencia Híbrida**: `brain/decisions/consistency-strategy.md`
- **Deployment Strategy**: `brain/decisions/deployment-strategy.md`
- **OpenAPI Auto-generado**: `brain/deployment/spec-kit-setup.md`

---

## 🆘 Troubleshooting

| Problema | Solución |
|----------|----------|
| MongoDB unhealthy | `docker exec eventflow_mongodb mongosh --eval "db.runCommand({ping:1})"` |
| Puerto 8001/8002/8003 ocupado | `lsof -ti:8001 \| xargs kill` |
| Redis connection refused | `docker compose logs redis` + `docker exec eventflow_redis redis-cli ping` |
| Tests fallan | `docker compose up -d` (BDs deben estar healthy) |
| Permisos volúmenes | `docker compose down -v && docker compose up -d --build` |

---

**Última actualización:** 2026-09-20  
**Versión:** 1.0.0  
**Estado:** Pre-defensa listo