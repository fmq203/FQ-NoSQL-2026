---
name: microservices-diagram
description: Diagrama de topología de microservicios EventFlow
metadata:
  type: architecture
  status: complete
---

# Diagrama de Microservicios — EventFlow

## Topología de Servicios

```mermaid
graph TB
    subgraph Client["Cliente / API Gateway"]
        UI[Frontend / Postman / JMeter]
    end

    subgraph Services["Microservicios"]
        US[Usuarios Service\n:8001]
        ES[Eventos Service\n:8002]
        RS[Reservas & Pagos Service\n:8003\nOrquestador SAGA]
    end

    subgraph Databases["Bases de Datos Políglotas"]
        MG[(MongoDB\n:27017\nUsuarios, Eventos, Reservas)]
        RD[(Redis\n:6379\nPagos atómicos, Cache, Inventario)]
        PG[(PostgreSQL\n:5432\nAudit Log, Event Sourcing)]
    end

    UI --> US
    UI --> ES
    UI --> RS

    US --> MG
    ES --> MG
    RS --> MG
    RS --> RD
    RS --> PG

    RS -.->|HTTP REST| US
    RS -.->|HTTP REST| ES

    style RS fill:#ffeb3b,stroke:#fbc02d,stroke-width:2px
    style MG fill:#4caf50,stroke:#388e3c,stroke-width:2px,color:#fff
    style RD fill:#ff5722,stroke:#e64a19,stroke-width:2px,color:#fff
    style PG fill:#2196f3,stroke:#1976d2,stroke-width:2px,color:#fff
```

---

## Descripción de Interacciones

### 1. Cliente → Servicios (Directo)
- **GET /api/usuarios/{id}** → Usuarios Service → MongoDB
- **GET /api/eventos/{id}** → Eventos Service → MongoDB
- **POST /api/reservar** → Reservas Service (Orquestador)

### 2. Reservas Service → Otros Servicios (Orquestación SAGA)
```
POST /api/reservar
    │
    ├─► GET /api/usuarios/{usuario_id}     (Validar usuario existe)
    │
    ├─► GET /api/eventos/{evento_id}       (Validar evento + aforo)
    │
    ├─► Redis: Lua Script (Pago atómico + Decremento inventario)
    │
    ├─► MongoDB: Insert Reserva
    │
    └─► PostgreSQL: Insert Audit Event
```

### 3. Flujos de Datos por Base de Datos

| Base de Datos | Escritura | Lectura |
|---------------|-----------|---------|
| **MongoDB** | Usuarios, Eventos, Reservas | Usuarios, Eventos, Historial |
| **Redis** | Pago (Lua), Inventario temporal | Cache disponibilidad |
| **PostgreSQL** | Audit log (Event Sourcing) | Reportes, Compliance |

---

## Puertos y Health Checks

| Servicio | Puerto | Health Endpoint |
|----------|--------|-----------------|
| Usuarios | 8001 | GET /health |
| Eventos | 8002 | GET /health |
| Reservas | 8003 | GET /health |
| MongoDB | 27017 | `db.runCommand({ping:1})` |
| Redis | 6379 | `redis-cli ping` |
| PostgreSQL | 5432 | `pg_isready` |

---

## Red Docker

```yaml
networks:
  eventflow_network:
    driver: bridge
```

Todos los servicios comparten la red `eventflow_network` para comunicación interna por nombre de servicio.

---

## Volúmenes Persistentes

```yaml
volumes:
  mongodb_data:    # Datos MongoDB
  redis_data:      # Datos Redis (AOF)
  postgresql_data: # Datos PostgreSQL
```