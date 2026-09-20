---
name: consistency-strategy
description: Estrategia de consistencia según operación
metadata:
  type: decision
  status: draft
---

# Estrategia de Consistencia

## Principio CAP para EventFlow

### Lectura (Eventos, Usuarios)
- **Prioridad:** Disponibilidad + Tolerancia a particiones
- **Modelo:** Eventual consistency (AP)
- **Implementación:** MongoDB con read preference `secondaryPreferred`, Redis caché
- **TTL:** 5-10 min en caché

### Escritura (Reservas, Pagos)
- **Prioridad:** Consistencia + Tolerancia a particiones
- **Modelo:** Strong consistency (CP)
- **Implementación:** Redis atomic transactions + MongoDB acknowledgement
- **Patrón:** SAGA orquestado con compensaciones

---

## Flujo Crítico: Compra de Entrada

1. **Usuario solicita reserva** → Valida en MongoDB (eventual OK)
2. **Reserva se procesa en Redis** (atomic, strong consistency)
3. **Pago se procesa en Redis** (atomic, strong consistency)
4. **Escritura se propaga a MongoDB** (MongoDB update → log de eventos)
5. **Evento de confirmación** se registra en log

---

## Manejo de Fallos

- Redis down → SAGA rollback (compensación)
- MongoDB down → Redis mantiene estado transitorio (buffer)
- Ambas down → Transacción falla explícitamente

---

## Estatus: Draft

Requiere validación del equipo en primeras sesiones.
