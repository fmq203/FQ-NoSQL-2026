# EventFlow - Plataforma de Gestión de Eventos

> **Tarea 2 NoSQL** - Diseño e implementación de un sistema de microservicios con bases de datos políglotas, consistencia eventual/fuerte, y patrones SAGA + Chain of Responsibility.

---

## 🏗️ Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Usuarios       │     │  Eventos        │     │  Reservas       │
│  Service        │     │  Service        │     │  & Pagos        │
│  (Puerto 8001)  │     │  (Puerto 8002)  │     │  Service        │
│                 │     │                 │     │  (Puerto 8003)  │
│  - CRUD Usuarios│     │  - CRUD Eventos │     │                 │
│  - Historial    │     │  - Health Check │     │  - SAGA         │
│  - Export GDPR  │     │  - Validación   │     │  - Chain of     │
└────────┬────────┘     └────────┬────────┘     │    Responsibility│
         │                       │              └────────┬────────┘
         │                       │                       │
    ┌────▼────────┐     ┌────────▼────────┐     ┌────────▼────────┐
    │   MongoDB   │     │   MongoDB       │     │   Redis         │
    │   (Usuarios)│     │   (Eventos)     │     │   (Inventario   │
    │             │     │                 │     │    atómico)     │
    └─────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                               ┌────────▼────────┐
                                               │   PostgreSQL    │
                                               │   (Pagos)       │
                                               └─────────────────┘
```

### Servicios

| Servicio | Puerto | Base de Datos | Responsabilidad |
|----------|--------|---------------|-----------------|
| **Usuarios** | 8001 | MongoDB | CRUD usuarios, historial compras, exportación GDPR |
| **Eventos** | 8002 | MongoDB | CRUD eventos, validación aforo, health check |
| **Reservas** | 8003 | Redis + PostgreSQL | Orquestador SAGA, pagos, inventario atómico |

### Bases de Datos

| BD | Uso | Justificación |
|----|-----|---------------|
| **MongoDB** | Usuarios, Eventos | Documentos flexibles, escalabilidad horizontal, consultas ricas |
| **Redis** | Inventario atómico | Operaciones atómicas Lua, sub-milisegundo, TTL |
| **PostgreSQL** | Pagos | ACID, transacciones financieras, integridad referencial |

---

## 🚀 Inicio Rápido

### Prerrequisitos
- Docker 24+ y Docker Compose 2.20+
- Make (opcional, para comandos simplificados)

### Levantar todo el stack

```bash
# Opción 1: Con Make (recomendado)
make up

# Opción 2: Directo con Docker Compose
docker compose up -d
```

### Verificar que todo funciona

```bash
# Verificar health checks
make health

# O manualmente
curl http://localhost:8001/health  # Usuarios
curl http://localhost:8002/health  # Eventos
curl http://localhost:8003/health  # Reservas
```

### Ver logs

```bash
make logs           # Todos los servicios
make logs-svc SVC=eventos-service  # Servicio específico
```

### Detener

```bash
make down
```

---

## 📋 Endpoints Principales

### Usuarios Service (`http://localhost:8001`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/usuarios` | Crear usuario |
| GET | `/api/usuarios/{id}` | Obtener usuario |
| GET | `/api/usuarios` | Listar usuarios (paginado) |
| GET | `/api/usuarios/exportar` | Exportar anonimizado (GDPR) |
| GET | `/health` | Health check |

**Ejemplo crear usuario:**
```bash
curl -X POST http://localhost:8001/api/usuarios \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_documento": "DNI",
    "nro_documento": "12345678",
    "nombre": "Juan",
    "apellido": "Pérez",
    "email": "juan.perez@example.com"
  }'
```

### Eventos Service (`http://localhost:8002`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/eventos` | Crear evento |
| GET | `/api/eventos/{id}` | Obtener evento |
| GET | `/health` | Health check |

**Ejemplo crear evento:**
```bash
curl -X POST http://localhost:8002/api/eventos \
  -H "Content-Type: application/json" \
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

### Reservas Service (`http://localhost:8003`)

> **Nota:** el MVP no versiona la API — las rutas son `/api/reservar` sin
> prefijo `v1`, alineadas al contrato exacto de la tarea. `APIVersioningMiddleware`
> existe como código pero no está registrado en `main.py` (decisión consciente,
> YAGNI); ver `.specify/specs/003-reservation-payment/spec.md`.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/reservar` | Iniciar SAGA reserva (idempotente por `reserva_id`) |
| GET | `/api/reservar/{id}` | Obtener reserva por ID |
| GET | `/api/reservar` | Listar reservas (paginado; filtros opcionales `usuario_id`, `evento_id`, `estado`) |
| GET | `/health` | Health check con dependencias |
| GET | `/metrics` | Métricas Prometheus |

**Ejemplo crear reserva:**
```bash
curl -X POST http://localhost:8003/api/reservar \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
    "evento_id": "550e8400-e29b-41d4-a716-446655440001",
    "cantidad": 2,
    "categoria": "general",
    "metodo_pago": "tarjeta"
  }'
```

**Resiliencia HTTP a Usuarios/Eventos Service** (`src/services/http_clients.py`):
- Reintentos: 3x con backoff exponencial (0.5s, 1s, 2s) ante timeout/error de red/5xx.
- Circuit breaker: `closed` → `open` tras 5 fallos consecutivos → `half-open` automático a los 30s (1 sola request de prueba) → `closed` si tiene éxito, `open` de nuevo si falla.

---

## 🏥 Health Checks

Todos los servicios exponen `/health` con 3 estados:

| Estado | Significado | HTTP |
|--------|-------------|------|
| `healthy` | Todo OK, latencia < 50ms | 200 |
| `degraded` | Latencia alta (50-500ms) | 200 |
| `unhealthy` | Dependencia caída | 503 |

**Respuesta ejemplo:**
```json
{
  "status": "healthy",
  "checks": {
    "mongodb": "ok",
    "redis": "ok",
    "postgresql": "ok",
    "usuarios_service": "ok",
    "eventos_service": "ok"
  },
  "service": "reservas-service",
  "version": "1.0.0",
  "timestamp": "2026-09-25T11:47:06.038620Z"
}
```

---

## 📊 Métricas Prometheus

Disponible en `/metrics` en cada servicio:

```bash
curl http://localhost:8002/metrics
```

Métricas expuestas:
- `http_requests_total` - Contador por método/endpoint/status
- `http_request_duration_seconds` - Histograma de latencia
- `http_requests_in_progress` - Requests en curso

---

## 🔄 Patrones Implementados

### SAGA Orchestration (Reservas Service)

El **Servicio de Reservas** actúa como **Orquestador Central**:

```
┌─────────────┐
│  Iniciar    │
│  SAGA       │
└──────┬──────┘
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Validar     │────▶│ Validar     │────▶│ Reservar    │────▶│ Procesar    │────▶│ Confirmar   │
│ Usuario     │     │ Evento/     │     │ Inventario  │     │ Pago        │     │ Reserva     │
│ (Usuarios   │     │ Aforo       │     │ (Redis      │     │ (PostgreSQL)│     │ (MongoDB)   │
│  Service)   │     │ (Eventos    │     │  Lua atómico)     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                                                                       │
       ▼                                                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPENSACIONES AUTOMÁTICAS EN CASO DE FALLO              │
│  • Liberar inventario Redis    • Cancelar pago    • Marcar reserva fallida  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Compensaciones automáticas** en caso de fallo en cualquier paso.

### Chain of Responsibility (Reservas Service)

Validaciones secuenciales en cadena:

```
Request ──▶ ValidadorDatos ──▶ ValidadorInventario ──▶ ProcesadorPago ──▶ ConfirmadorReserva
              │                    │                      │                    │
              ▼                    ▼                      ▼                    ▼
         Datos válidos        Stock suficiente        Pago OK            Reserva creada
```

---

## 🛡️ RFC 7807 Error Handling

Todos los errores siguen **RFC 7807 Problem Details**, con códigos específicos por escenario (no genéricos por status HTTP):

```json
{
  "type": "https://eventflow.example.com/errors/INSUFFICIENT_INVENTORY",
  "title": "Conflict",
  "status": 409,
  "detail": "Inventario insuficiente",
  "instance": "/api/reservar",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Códigos principales (Reservas Service):** `VALIDATION_ERROR` (400/422), `USER_NOT_FOUND`/`EVENT_NOT_FOUND`/`RESERVA_NOT_FOUND` (404), `EVENT_NOT_AVAILABLE`/`INSUFFICIENT_INVENTORY` (409), `PAYMENT_FAILED`/`RESERVATION_FAILED`/`INTERNAL_ERROR` (500), `SERVICE_UNAVAILABLE` (503 — dependencia caída o circuit breaker abierto).

**Headers de tracing:** `X-Correlation-ID`, `X-Trace-ID` en todas las respuestas.

---

## 📈 CQRS Analítico (Reservas Service)

Además del modelo operativo (MongoDB), `event_log` en PostgreSQL expone vistas de solo lectura para consultas de negocio, creadas en `init_pg_schema()`:

| Vista | Contenido |
|-------|-----------|
| `ventas_por_evento` | Reservas confirmadas, entradas e ingreso total por evento (últimos 30 días) |
| `tasa_exito_saga` | % de SAGAs exitosas vs fallidas por día (últimos 7 días) |
| `compensaciones_por_tipo` | Compensaciones ejecutadas agrupadas por paso (últimas 24h) |

Más un índice GIN (`idx_event_log_payload_gin`) para acelerar los filtros por campos del `payload` JSONB. El particionamiento mensual de `event_log` queda documentado pero sin implementar — su propio criterio de activación (>10M eventos/mes) no se alcanza en este proyecto.

---

## 🧪 Tests

```bash
# Todos los tests
make test

# Solo unitarios
make test-unit

# Solo integración
make test-integration

# Solo contrato
make test-contract
```

**Estructura de tests por servicio:**
```
servicio/
├── tests/
│   ├── contract/      # Tests de contrato (API, RFC 7807, OpenAPI/schemathesis)
│   ├── integration/   # Tests de integración (BD real vía docker-compose)
│   ├── unit/          # Tests unitarios (mocked)
│   └── performance/   # Tests de latencia (p95/p99)
```

**Estado (2026-09-26), suite completa contra `docker compose up -d`:**

| Servicio | Resultado |
|----------|-----------|
| usuarios-service | 38/38 ✅ |
| eventos-service | 80/80 ✅ |
| reservas-service | 100 passed / 4 skipped / 1 flaky (test de p99 bajo carga concurrente — timing-sensitive, confirmado que pasa en corridas aisladas) |

---

## 📁 Estructura del Proyecto

```
TAREA 2/
├── Makefile                    # Comandos unificados
├── docker-compose.yml          # Stack completo (3 DBs + 3 servicios)
├── README.md                   # Este archivo
├── .gitignore
├── .specify/                   # Spec-kit (especificaciones)
│   └── specs/
│       ├── 001-usuarios-crud/
│       ├── 002-eventos-crud/
│       └── 003-reservation-payment/
├── brain/                      # Documentación técnica (Second Brain)
│   ├── decisions/              # Decisiones arquitectónicas
│   ├── architecture/           # Diagramas y overview
│   ├── microservices/          # Specs por servicio
│   ├── endpoints/              # APIs REST
│   ├── data-models/            # Schemas NoSQL
│   ├── patterns/               # SAGA, Chain of Responsibility
│   ├── deployment/             # Docker, specs
│   └── learnings/              # Lecciones aprendidas
├── usuarios-service/           # Microservicio Usuarios
│   ├── src/
│   │   ├── api/routes/         # Endpoints
│   │   ├── api/middleware/     # Correlation, logging, metrics
│   │   ├── services/           # Lógica de negocio
│   │   ├── models/             # Pydantic models
│   │   └── utils/              # Errors, validation
│   ├── tests/                  # Contract, integration, unit, performance
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
├── eventos-service/            # Microservicio Eventos (mismo patrón)
└── reservas-service/           # Microservicio Reservas (SAGA orchestrator)
```

---

## 📚 Documentación Técnica (Brain)

Toda la documentación de decisiones y arquitectura está en `brain/`:

| Archivo | Descripción |
|---------|-------------|
| `brain/README.md` | Índice maestro del Second Brain |
| `brain/CLAUDE.md` | Mapa de navegación para IA |
| `brain/decisions/db-selection.md` | Justificación MongoDB + Redis |
| `brain/decisions/consistency-strategy.md` | Eventual vs Strong consistency |
| `brain/patterns/saga-pattern.md` | Detalles SAGA Orchestration |
| `brain/patterns/chain-of-responsibility-pattern.md` | Chain of Responsibility |
| `brain/architecture/overview.md` | Vista general arquitectura |
| `brain/architecture/saga-flow.md` | Diagrama flujo SAGA |
| `brain/architecture/chain-of-responsibility.md` | Diagrama CoR |

---

## 🛠️ Desarrollo

### Hot Reload (modo desarrollo)

```bash
# Usuarios
make dev-usuarios

# Eventos
make dev-eventos

# Reservas
make dev-reservas
```

### Shell en contenedores

```bash
make shell-usuarios
make shell-eventos
make shell-reservas
make shell-mongo
make shell-redis
make shell-pg
```

### Reconstruir un servicio

```bash
docker compose build --no-cache eventos-service
docker compose up -d eventos-service
```

---

## 📦 CI/CD

```bash
# Pipeline completo
make ci

# Verificación completa
make verify
```

---

## 📅 Fechas Clave

| Hito | Fecha |
|------|-------|
| Pre-defensa | Jueves 5 de noviembre 2026 |
| Defensa final | Jueves 12 de noviembre 2026 |
| Tiempo presentación | ~12 min (demo + arquitectura) |

---

## 🤝 Equipo

Desarrollado para **Tarea 2 NoSQL** - EventFlow Platform.

---

## 📄 Licencia

Proyecto académico - Uso educativo.