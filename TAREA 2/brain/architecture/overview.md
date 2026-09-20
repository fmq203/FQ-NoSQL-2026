---
name: architecture-overview
description: Vista general de la arquitectura de microservicios
metadata:
  type: architecture
  status: in-progress
---

# Arquitectura EventFlow — Overview

## Componentes Principales

```
┌─────────────────────────────────────────────────────────────────┐
│                  CLIENTE / API GATEWAY                          │
└────────────┬────────────────┬────────────────┬──────────────────┘
             │                │                │
      ┌──────▼──┐      ┌──────▼──┐      ┌──────▼──────────┐
      │ Usuarios │      │ Eventos │      │ Reservas/Pagos │
      │ Service  │      │ Service │      │ Service (Orch) │
      └──────┬──┘      └──────┬──┘      └──────┬──────────┘
             │                │                │
      ┌──────▼────────────────▼────────────────▼────────┐
      │   DATOS OPERACIONALES (MongoDB + Redis)        │
      │  ┌──────────────┐  ┌──────────────────┐        │
      │  │  MongoDB     │  │  Redis (Atomic)  │        │
      │  │ (Usuarios,   │  │  (Pagos,         │        │
      │  │  Eventos,    │  │   Caché,         │        │
      │  │  Historial)  │  │   Reservas temp) │        │
      │  └──────────────┘  └──────────────────┘        │
      └────────────┬─────────────────────────────────────┘
                   │
                   │ (Sync - Eventual)
                   │
      ┌────────────▼────────────────────────────────────┐
      │   AUDITORÍA & COMPLIANCE (PostgreSQL)           │
      │  ┌──────────────────────────────────────────┐   │
      │  │  Event Log (Append-Only, Immutable)      │   │
      │  │  • RESERVA_CREADA                        │   │
      │  │  • PAGO_PROCESADO / PAGO_REVERTIDO       │   │
      │  │  • DATOS_PERSONALES_MODIFICADOS (GDPR)   │   │
      │  │  • Auditoría completa (quién, cuándo)    │   │
      │  └──────────────────────────────────────────┘   │
      └─────────────────────────────────────────────────┘
```

---

## Patrones de Diseño

### SAGA Orchestration (Reservas & Pagos)
```
┌─────────────────────────┐
│ Reserva Service (Orch)  │
│   Coordinator           │
└──────────┬──────────────┘
           │
     ┌─────┴──────────────────────┐
     │                            │
     ▼                            ▼
┌─────────────┐          ┌──────────────┐
│ Step 1:     │          │ Step 2:      │
│ Validar     │─────────▶│ Procesador   │
│ Inventario  │          │ de Pagos     │
└─────────────┘          └──────┬───────┘
                                │
                                ▼
                         ┌─────────────────┐
                         │ Step 3: Confirmar│
                         │ en MongoDB      │
                         └─────────────────┘
```

**Compensations (en caso de fallo):**
- Pago falló → liberar inventario
- Confirmación falló → revertir pago (crédito)

### Chain of Responsibility (Validaciones)
```
Solicitud de Reserva
    │
    ▼
┌──────────────────────┐
│ ValidadorDatos       │
│ (campos obligatorios)│
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ ValidadorInventario  │
│ (aforo disponible)   │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ ProcesadorDePago     │
│ (transacción)        │
└────────┬─────────────┘
         │
         ▼
    Reserva Confirmada
```

---

## Microservicios

### Servicio de Usuarios
- **Responsabilidad:** CRUD usuarios, historial de compras
- **BD:** MongoDB (colección `usuarios`)
- **Consistency:** Eventual (AP)
- **Endpoints:** POST /usuarios, GET /usuarios/{id}

### Servicio de Eventos
- **Responsabilidad:** CRUD eventos, disponibilidad de entradas
- **BD:** MongoDB (colección `eventos`)
- **Consistency:** Eventual (AP)
- **Endpoints:** POST /eventos, GET /eventos/{id}

### Servicio de Reservas y Pagos (Orquestador)
- **Responsabilidad:** Procesar reservas (SAGA orchestrator), pagos
- **BD:** Redis (estructuras con TTL para transacciones)
- **Consistency:** Strong (CP)
- **Endpoints:** POST /reservar
- **Patrón:** SAGA + Chain of Responsibility

---

## Flujo de Datos: Compra de Entrada (3 BDs)

```
1. Usuario hace POST /reservar
   │
2. Reservas Service (Orch) inicia SAGA
   │
3. Step 1: Valida usuario + evento
   └─ MongoDB: eventual consistency OK
   
4. Step 2: Valida inventario
   └─ MongoDB: busca disponibles
   
5. Step 3: Procesa pago (Redis atomic)
   └─ Redis Lua script: transacción indivisible
      (no hay race conditions)
   
6. Step 4: Decrementa aforo
   └─ MongoDB + Redis: actualiza inventario
   
7. Step 5: Registra reserva
   └─ MongoDB: documento de reserva confirmada
   
8. ✅ Step 6: AUDITORÍA en PostgreSQL (append-only)
   └─ INSERT event_log { tipo: 'RESERVA_CREADA', datos: {...} }
      (registro inmutable para compliance & debugging)
   
9. ✅ Confirma transacción O ❌ Rollback con compensaciones
   └─ Si falla en Step 5: PostgreSQL registra RESERVA_FALLIDA
      (completa trazabilidad de qué salió mal)
```

---

## Escalabilidad

- **MongoDB:** Sharding por evento_id (hot events)
- **Redis:** Cluster o Sentinel para HA
- **Microservicios:** Stateless (escalables horizontalmente)
- **Caché:** Redis TTL invalidación (eventual consistency de lecturas)

---

## Próximos Documentos

- [[microservices-diagram]] — Diagrama detallado
- [[saga-flow]] — SAGA flow diagram
- [[chain-of-responsibility-diagram]] — CoR diagram
