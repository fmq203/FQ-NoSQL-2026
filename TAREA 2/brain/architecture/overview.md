---
name: overview
description: Vista general de la arquitectura EventFlow
metadata:
  type: architecture
  status: complete
---

# EventFlow — Arquitectura General

## Contexto

**EventFlow** es una plataforma de gestión de eventos y venta de entradas construida con arquitectura de microservicios. Diseñada para alto volumen de transacciones y consultas, aplicando bases de datos políglotas, patrones de consistencia distribuida y principios de escalabilidad.

---

## Microservicios

| Servicio | Puerto | Responsabilidad Principal | Base de Datos |
|----------|--------|---------------------------|---------------|
| **Usuarios** | 8001 | Perfiles, historial de compras, exportación anonimizada | MongoDB |
| **Eventos** | 8002 | Información de eventos, aforo, disponibilidad | MongoDB |
| **Reservas y Pagos** | 8003 | Orquestador SAGA, Chain of Responsibility, procesamiento transaccional | Redis (pagos atómicos), MongoDB (reservas), PostgreSQL (auditoría) |

---

## Bases de Datos (Políglota)

| DB | Tipo | Uso | Justificación |
|----|------|-----|---------------|
| **MongoDB** | Documental | Usuarios, Eventos, Reservas | Flexibilidad esquema, embedded documents, consultas rápidas |
| **Redis** | Clave-Valor (In-memory) | Pagos atómicos, inventario temporal, cache | Operaciones atómicas Lua, alta velocidad, TTL automático |
| **PostgreSQL** | Relacional | Audit log, event sourcing | ACID, consultas complejas, compliance |

---

## Patrones Implementados

| Patrón | Ubicación | Propósito |
|--------|-----------|-----------|
| **SAGA Orchestration** | Reservas Service | Transacción distribuida compra de entradas |
| **Chain of Responsibility** | Reservas Service | Validaciones secuenciales (datos, inventario, pago) |
| **Event Sourcing + CQRS** | Reservas Service (PostgreSQL) | Auditoría completa, separación lectura/escritura |
| **Anonimización Irreversible** | Usuarios Service | GDPR compliance en exportación masiva |

---

## Estrategia de Consistencia

| Operación | Consistencia | Justificación |
|-----------|--------------|---------------|
| Lectura usuarios/eventos | **Eventual** | Alta disponibilidad, tolerancia a particiones, escalabilidad |
| Escritura reservas/pagos | **Fuerte (ACID)** | Unicidad reserva, no doble venta, integridad financiera |

---

## Comunicación

- **Síncrona**: HTTP/REST entre servicios (Reservas → Usuarios, Reservas → Eventos)
- **Asíncrona**: Event log en PostgreSQL para auditoría y Event Sourcing
- **Atómica**: Lua scripts en Redis para pago + decremento inventario

---

## Despliegue

- **Docker Compose** para desarrollo local
- **Health checks** en todos los servicios
- **Red compartida** `eventflow_network`
- **Volúmenes persistentes** para MongoDB, Redis, PostgreSQL

---

## Endpoints Principales

```
Usuarios (8001):
  POST   /api/usuarios           → Crear usuario
  GET    /api/usuarios           → Listar (paginado)
  GET    /api/usuarios/{id}      → Obtener con historial
  GET    /api/usuarios/exportar  → Exportar anonimizado (GDPR)

Eventos (8002):
  POST   /api/eventos            → Crear evento
  GET    /api/eventos/{id}       → Obtener con aforo disponible

Reservas (8003):
  POST   /api/reservar           → SAGA + Chain of Responsibility
```

---

## Diagramas Relacionados

- [[microservices-diagram]] — Topología de servicios
- [[data-flow]] — Flujo de datos entre servicios
- [[saga-flow]] — Flujo transacción SAGA
- [[chain-of-responsibility]] — Cadena de validaciones