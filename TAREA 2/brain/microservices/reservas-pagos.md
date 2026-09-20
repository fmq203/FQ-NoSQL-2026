---
name: reservas-pagos-service
description: Especificación del Servicio de Reservas y Pagos (Orquestador SAGA)
metadata:
  type: specification
  status: in-progress
---

# Servicio de Reservas y Pagos

## Responsabilidades

- **Orquestador SAGA:** Coordina la transacción distribuida de compra
- **Procesador de Pagos:** Maneja la lógica transaccional (atomic)
- **Validador:** Chain of Responsibility para validaciones

## Base de Datos

- **BD Primaria:** Redis (para transacciones atómicas)
- **BD Secundaria:** MongoDB (para historial de reservas)
- **Consistency:** Strong (CP) — No hay dobles ventas

## Endpoints

Ver [[reservas-endpoints]]

## Patrones

- **SAGA Orchestration:** Ver [[saga-pattern]]
  - Orquestador: Reservas Service
  - Pasos: Validar datos → Validar inventario → Procesar pago → Confirmar en MongoDB
  - Compensaciones: Revertir pago, liberar inventario

- **Chain of Responsibility:** Ver [[chain-of-responsibility-pattern]]
  - ValidadorDatos
  - ValidadorInventario
  - ProcesadorDePago
  - ConfirmadorTransaccion

## Flujo Crítico

```
POST /api/reservar
  ↓
Chain of Responsibility (validaciones)
  ↓
SAGA Orchestrator (transacción distribuida)
  ├─ Step 1: Validar usuario (GET /usuarios/{id})
  ├─ Step 2: Validar evento (GET /eventos/{id})
  ├─ Step 3: Procesar pago en Redis (atomic)
  ├─ Step 4: Decrementar inventario (evento)
  └─ Step 5: Confirmar en MongoDB
  ↓
✅ Reserva Confirmada O ❌ Rollback
```

## Interacciones

- **GET /usuarios/{id}** — Usuarios Service
- **GET /eventos/{id}** — Eventos Service
- **POST /eventos/{id}/decrement-tickets** — Eventos Service (SAGA Step 4)

## Notas

- **Criticidad:** MÁS CRÍTICO del sistema
- **Garantías:** Atomicidad (Lua scripts en Redis)
- **Timeout:** Transacciones < 5 segundos (TTL en Redis)
- **Logging:** Event log para auditoria y debugging
