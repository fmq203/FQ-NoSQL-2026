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
| POST | `/api/v1/eventos` | Crear evento |
| GET | `/api/v1/eventos/{id}` | Obtener evento |
| GET | `/health` | Health check |

**Ejemplo crear evento:**
```bash
curl -X POST http://localhost:8002/api/v1/eventos \
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

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/reservar` | Iniciar SAGA reserva |
| GET | `/api/v1/reservar/{id}` | Obtener reserva |
| GET | `/health` | Health check con dependencias |
| GET | `/metrics` | Métricas Prometheus |

**Ejemplo crear reserva:**
```bash
curl -X POST http://localhost:8003/api/v1/reservar \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
    "evento_id": "550e8400-e29b-41d4-a716-446655440001",
    "cantidad": 2,
    "categoria": "General"
  }'
```

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

Todos los errores siguen **RFC 7807 Problem Details**:

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

**Headers de tracing:** `X-Correlation-ID`, `X-Trace-ID` en todas las respuestas.

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
│   ├── contract/      # Tests de contrato (API)
│   ├── integration/   # Tests de integración (BD real)
│   ├── unit/          # Tests unitarios (mocked)
│   └── performance/   # Tests de latencia (p95/p99)
```

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