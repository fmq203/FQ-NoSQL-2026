---
name: three-database-strategy
description: Estrategia de 3 bases de datos - MongoDB, Redis, PostgreSQL
metadata:
  type: decision
  status: in-progress
  last-updated: 2026-09-20
---

# Estrategia de 3 Bases de Datos

## Arquitectura

```
                   EVENTFLOW 3-DATABASE ARCHITECTURE

┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  MONGODB         │    │  REDIS          │    │  POSTGRESQL      │
│  (Datos maestros)│    │  (Transacciones)│    │  (Auditoría)     │
├──────────────────┤    ├─────────────────┤    ├──────────────────┤
│ Usuarios         │    │ Pagos (atomic)  │    │ Event Log        │
│ Eventos          │    │ Reservas temp   │    │ Compliance Log   │
│ Sesiones         │    │ Caché caliente  │    │ Auditoría        │
│ Historial        │    │                 │    │ GDPR Tracking    │
│                  │    │ TTL: 5-90 días  │    │                  │
└──────────────────┘    └─────────────────┘    └──────────────────┘
     AP (Eventual)          CP (Strong)             CA (ACID logs)
```

---

## Responsabilidades por BD

### 📊 MongoDB — Datos de Negocio

**Qué almacena:**
- Usuarios (perfil, email, documento)
- Eventos (nombre, fecha, lugar, aforo)
- Historial de compras (embebido en usuarios)
- Sesiones de usuario

**Características:**
- Escalabilidad horizontal (sharding)
- Flexible schema (puede evolucionar)
- Búsquedas rápidas (indexes)
- **Consistency:** AP (Eventual) — OK para lecturas

**Ejemplo:**
```javascript
db.usuarios.findOne({ email: "juan@example.com" })
// Retorna: usuario completo con historial
```

---

### ⚡ Redis — Transacciones Críticas

**Qué almacena:**
- Reservas en proceso (transacciones)
- Pagos (pendientes, completados)
- Caché de eventos/usuarios (TTL 5-10 min)
- Sesiones (TTL horas)

**Características:**
- In-memory ultra-rápido (< 10ms)
- Transacciones atómicas (Lua scripts)
- No hay race conditions
- Persistence (RDB/AOF) como backup
- **Consistency:** CP (Strong) — NO hay dobles ventas

**Ejemplo:**
```lua
-- Lua script: procesar pago atomically
if redis.call('GET', 'evento:123:disponibles') >= 2 then
  redis.call('DECRBY', 'evento:123:disponibles', 2)
  redis.call('INCR', 'pago:completados')
  return { ok = true }
else
  return { err = "Inventario insuficiente" }
end
```

---

### 📋 PostgreSQL — Auditoría e Compliance

**Qué almacena:**
- **Event Log (append-only):** Cada evento importante queda registrado
- **Compliance Log:** Quién accedió qué, cuándo
- **GDPR Tracking:** Modificaciones a datos personales
- **Debugging:** Replay de transacciones fallidas

**Características:**
- ACID transactions (garantía fuerte)
- Ordered by timestamp (auditoría temporal)
- Immutable (append-only pattern)
- SQL para análisis histórico
- **Consistency:** CA (ACID logs)

**Ejemplo — Event Log:**
```sql
INSERT INTO event_log (evento_id, tipo, usuario_id, datos, timestamp)
VALUES (
  'uuid-123',
  'RESERVA_CREADA',
  'user-456',
  '{"evento_id":"evt-789","cantidad":2,"precio":300}',
  NOW()
);

-- Luego: SELECT * FROM event_log WHERE usuario_id = 'user-456' ORDER BY timestamp
-- Auditoría completa de todo lo que hizo ese usuario
```

---

## Flujo de Transacción Exitosa (3 BDs)

```
1. POST /api/reservar
   │
   ├─ Validar en MongoDB
   │  └─ GET usuarios/{id}, eventos/{id}
   │     (eventual consistency OK)
   │
   ├─ Procesar en Redis (ATOMIC)
   │  └─ Lua script: pago + decrement inventario
   │     (strong consistency garantizada)
   │
   ├─ Confirmar en MongoDB
   │  └─ UPDATE eventos{} (inventario final)
   │     db.reservas.insert() (registro de compra)
   │
   └─ AUDITORÍA en PostgreSQL (APPEND-ONLY)
      └─ INSERT event_log { tipo: 'RESERVA_CREADA', usuario_id, ... }
         (immutable timestamp, para debugging SAGA)

Result: 201 Created
```

---

## Casos de Uso Específicos

### 1. Debuggear por qué falló una compra

**Problema:** Un usuario reporta que su compra falló pero le cobraron.

**Solución:**
```sql
-- PostgreSQL: ver exactamente qué pasó
SELECT * FROM event_log 
WHERE usuario_id = 'user-456' 
  AND tipo IN ('RESERVA_INICIADA', 'PAGO_PROCESADO', 'RESERVA_CONFIRMADA', 'PAGO_REVERTIDO')
ORDER BY timestamp;

-- Resultado: puede ver toda la timeline de su transacción fallida
```

---

### 2. Compliance & GDPR

**Problema:** Usuario solicita "derecho al olvido" (GDPR).

**Solución:**
```sql
-- PostgreSQL: registro de todas las modificaciones de datos personales
SELECT * FROM event_log 
WHERE tipo = 'DATOS_PERSONALES_MODIFICADOS' 
  AND usuario_id = 'user-456';

-- Resultado: historial completo de cambios, antes/después
```

---

### 3. Análisis de Eventos Problemáticos

**Problema:** El evento "Concierto 2026" tiene muchas transacciones fallidas.

**Solución:**
```sql
-- PostgreSQL: análisis de fallos por evento
SELECT 
  COUNT(*) as fallos,
  tipo,
  DATE(timestamp) as fecha
FROM event_log
WHERE evento_id = 'evt-concierto-2026'
  AND tipo LIKE '%FALLIDA%'
GROUP BY tipo, fecha;
```

---

## Flujo de Compensación (Fallo en SAGA)

```
1. SAGA Step 3 falla (pago rechazado)
   │
   ├─ Redis: Rollback (revertir fondos)
   │
   ├─ MongoDB: No actualizar inventario
   │
   └─ PostgreSQL: Registrar evento de FALLO
      INSERT event_log {
        tipo: 'RESERVA_FALLIDA',
        razon: 'PAGO_RECHAZADO',
        timestamp: NOW()
      }
      (Queda registro inmutable del fallo para auditoría)

Result: 500 Error + Auditoría completa del fallo
```

---

## Ventajas de 3 BDs

| Ventaja | Detalles |
|---------|----------|
| **Especialización** | Cada BD optimizada para su caso de uso |
| **Consistencia Flexible** | Eventual (MongoDB), Strong (Redis), ACID (PostgreSQL) |
| **Debuggabilidad** | PostgreSQL como "caja negra" (black box) para ver qué pasó |
| **Compliance** | Auditoría inmutable en PostgreSQL |
| **Escalabilidad** | MongoDB horizontal, Redis Cluster, PostgreSQL standby |
| **Performance** | Redis ultra-rápido para crítico, MongoDB para lectura, PostgreSQL para análisis offline |

---

## Desafíos

| Desafío | Mitigación |
|---------|-----------|
| **Complejidad operacional** | Documentación clara (este brain), scripts de deployment |
| **Sincronización entre BDs** | SAGA coordina, PostgreSQL es eventual (no es master) |
| **Backups** | Estrategia separada para cada BD |
| **Monitoring** | Dashboards que lean de las 3 BDs |

---

## Alternativas Rechazadas

### ❌ Solo MongoDB
- No garantiza atomicidad en pagos
- No tiene auditoria built-in

### ❌ MongoDB + Redis
- Sin auditoría legal/compliance
- Difícil debuggear transacciones fallidas

### ✅ MongoDB + Redis + PostgreSQL
- **Seleccionada:** Balancea performance + compliance + debuggabilidad

---

## Próximas Decisiones

- [ ] Schema de event_log en PostgreSQL (ver [[event-log-schema]])
- [ ] Política de retention: ¿cuánto tiempo guardar event log?
- [ ] Encryption de datos sensibles en PostgreSQL
- [ ] Backup strategy para 3 BDs
