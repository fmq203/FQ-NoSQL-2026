---
name: db-selection
description: Decisión de selección de bases de datos NoSQL para EventFlow
metadata:
  type: decision
  status: complete
---

# Decisión: Selección de Bases de Datos NoSQL

## Problema

EventFlow requiere almacenar datos heterogéneos con distintos patrones de acceso:
- Usuarios: Perfiles + historial de compras (documentos anidados)
- Eventos: Información + aforo dinámico (lecturas frecuentes, escrituras ocasionales)
- Reservas: Transacciones ACID + auditoría completa
- Pagos: Operaciones atómicas de alta concurrencia
- Cache/Inventario: Acceso ultra-rápido con TTL

Se deben elegir **al menos dos bases de datos NoSQL** y justificar su asignación a microservicios.

---

## Opciones Evaluadas

| Base de Datos | Tipo | Pros | Contras |
|---------------|------|------|---------|
| **MongoDB** | Documental | Esquema flexible, embedded documents, índices compuestos, aggregations, sharding nativo | No ACID transaccional multi-document (hasta 4.0), consistencia eventual por defecto |
| **Redis** | Clave-Valor (In-memory) | Sub-milisegundo, operaciones atómicas Lua, TTL nativo, pub/sub, estructuras ricas | Memoria limitada, persistencia opcional, no consultas complejas |
| **Cassandra** | Wide-column | Escalabilidad lineal, alta disponibilidad, tuneable consistency | Complejidad operacional, modelo de datos restrictivo, no joins |
| **DynamoDB** | Key-Value/Document | Serverless, escalado automático, DAX cache | Vendor lock-in, costos impredecibles, límites de item size |
| **Couchbase** | Documental + Key-Value | N1QL (SQL-like), memory-first, mobile sync | Licencia enterprise, complejidad |

---

## Decisión

### Asignación Final

| Microservicio | Base de Datos Primaria | Base de Datos Secundaria | Justificación |
|---------------|------------------------|--------------------------|---------------|
| **Usuarios** | **MongoDB** | — | Documentos anidados (historial_compras[]), consultas flexibles, embedded pattern natural |
| **Eventos** | **MongoDB** | Redis (cache) | Lecturas masivas de eventos, aforo dinámico, embedded para ubicaciones/precios |
| **Reservas y Pagos** | **Redis** (pagos) + **MongoDB** (reservas) + **PostgreSQL** (auditoría) | — | Redis: atomicidad Lua para pago+inventario; MongoDB: persistencia reserva; PostgreSQL: ACID audit log |

### Bases de Datos NoSQL Seleccionadas (Mínimo 2)

1. **MongoDB** — Base documental principal para Usuarios, Eventos, Reservas
2. **Redis** — Clave-valor in-memory para pagos atómicos, inventario temporal, cache

> **Nota**: PostgreSQL se usa como base relacional complementaria para auditoría/Event Sourcing (requerimiento de consistencia fuerte en escritura), no cuenta como NoSQL.

---

## Justificación Detallada

### MongoDB para Usuarios y Eventos

**Patrón Embedded vs Reference:**

- **Usuarios**: `historial_compras[]` **EMBEDDED** — Acceso frecuente junto al perfil, tamaño acotado (últimas 50 compras), atomicidad de actualización
- **Eventos**: `ubicacion`, `precios[]`, `categorias[]` **EMBEDDED** — Datos que siempre se leen juntos, no compartidos
- **Referencias**: `usuario_id` en Reservas, `evento_id` en Reservas — Relaciones many-to-one, consultas independientes

**Ventajas:**
- Un solo query trae usuario + historial (sin joins)
- Esquema flexible para agregar campos (ej: preferencias, notificaciones)
- Índices compuestos para consultas frecuentes (`email` unique, `nro_documento` unique)
- Sharding por `usuario_id` o `evento_id` para escalar

### Redis para Pagos e Inventario

**Por qué Redis + Lua Scripts:**

```lua
-- Operación ATÓMICA e INMEDIATA
-- 1. Verificar inventario
-- 2. Decrementar inventario  
-- 3. Registrar pago
-- TODO EN UNA SOLA LLAMADA DE RED
```

- **Atomicidad**: Lua scripts se ejecutan sin interleaving
- **Velocidad**: < 1ms latencia, crítico para alta concurrencia
- **TTL automático**: Limpieza de pagos pendientes/expirados
- **Estructuras**: Hash para pago, String para contador inventario

### PostgreSQL para Auditoría (Event Sourcing)

- **ACID completo** para compliance financiero
- **Event Log** inmutable: cada paso SAGA = evento
- **Consultas complejas**: Reportes, reconciliación, debugging
- **CQRS natural**: Escritura en event_log, lectura en vistas materializadas

---

## Alternativas Rechazadas

| Alternativa | Por qué NO |
|-------------|------------|
| Solo MongoDB | No garantiza atomicidad pago+inventario sin transacciones distribuidas complejas |
| Solo Redis | No apto para consultas ad-hoc, historial, exportación GDPR |
| Cassandra | Overkill para volumen actual, modelo de datos inadecuado para documentos anidados |
| DynamoDB | Vendor lock-in, costos variables, límites de item (400KB) para historial |

---

## Referencias

- [[data-models/db-choice-rationale]] — Razonamiento detallado por entidad
- [[architecture/overview]] — Vista general arquitectura
- [[patterns/saga-pattern]] — Uso de Redis en SAGA