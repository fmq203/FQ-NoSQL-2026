---
name: event-log-schema
description: Schema de Event Log en PostgreSQL (Append-Only)
metadata:
  type: specification
  status: draft
---

# Schema — Event Log (PostgreSQL)

## Tabla: `event_log`

```sql
CREATE TABLE event_log (
  -- Primary Key
  id BIGSERIAL PRIMARY KEY,
  
  -- Event Identification
  evento_id UUID NOT NULL,                    -- Identificador del evento
  tipo VARCHAR(100) NOT NULL,                 -- RESERVA_CREADA, PAGO_PROCESADO, etc
  
  -- Actor & Context
  usuario_id UUID,                            -- Quién hizo la acción (nullable para eventos del sistema)
  servicio_origen VARCHAR(50),                -- usuarios | eventos | reservas
  
  -- Data
  datos JSONB,                                -- Datos completos del evento (flexible)
  
  -- Auditoría
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ip_address INET,                            -- Para compliance
  user_agent TEXT,                            -- Para compliance
  
  -- Integridad (blockchain-like)
  hash_anterior UUID,                         -- Hash del evento anterior (chain)
  
  -- Control
  versión BIGINT DEFAULT 1,
  
  -- Indexes
  INDEX ON (usuario_id, timestamp DESC),
  INDEX ON (tipo, timestamp DESC),
  INDEX ON (evento_id),
  INDEX ON (timestamp DESC)  -- Búsquedas recientes rápidas
);
```

---

## Tipos de Eventos

```
RESERVA_INICIADA
├─ usuario_id: uuid
├─ evento_id: uuid
├─ cantidad: int
├─ precio_total: decimal
└─ timestamp

PAGO_PROCESADO
├─ usuario_id: uuid
├─ reserva_id: uuid
├─ monto: decimal
├─ metodo_pago: string
└─ resultado: 'éxito' | 'fallo'

PAGO_REVERTIDO
├─ usuario_id: uuid
├─ reserva_id: uuid
├─ monto: decimal
├─ razon: 'inventario_insuficiente' | 'error_sistema'

INVENTARIO_DECREMENTADO
├─ evento_id: uuid
├─ cantidad: int
├─ disponibles_despues: int

RESERVA_CONFIRMADA
├─ usuario_id: uuid
├─ reserva_id: uuid
├─ numero_confirmacion: string

RESERVA_FALLIDA
├─ usuario_id: uuid
├─ evento_id: uuid
├─ razon: string
├─ paso_fallo: int (1-5)

DATOS_PERSONALES_MODIFICADOS (GDPR)
├─ usuario_id: uuid
├─ campos_modificados: array
├─ valor_anterior: jsonb
├─ valor_nuevo: jsonb

EXPORTACION_DATOS_SOLICITADA (GDPR)
├─ usuario_id: uuid
├─ formato: 'json' | 'csv'
├─ timestamp_solicitud: timestamp
```

---

## Ejemplo: Insertar Evento de Reserva

```sql
INSERT INTO event_log 
  (evento_id, tipo, usuario_id, servicio_origen, datos, ip_address, user_agent, hash_anterior)
VALUES (
  'uuid-12345',
  'RESERVA_CONFIRMADA',
  'user-456',
  'reservas',
  jsonb_build_object(
    'reserva_id', 'res-789',
    'evento_id', 'evt-123',
    'cantidad', 2,
    'precio_total', 300.00,
    'numero_confirmacion', 'CONF-2026092010053012345'
  ),
  '192.168.1.100',
  'Mozilla/5.0...',
  (SELECT evento_id FROM event_log 
   WHERE usuario_id = 'user-456' 
   ORDER BY timestamp DESC LIMIT 1)
);
```

---

## Queries Comunes

### 1. Auditoría de Usuario (Timeline)

```sql
SELECT 
  timestamp,
  tipo,
  datos->>'reserva_id' as reserva_id,
  datos->>'precio_total' as precio
FROM event_log
WHERE usuario_id = 'user-456'
ORDER BY timestamp DESC
LIMIT 50;
```

### 2. Debugging: Por qué falló la compra?

```sql
SELECT 
  timestamp,
  tipo,
  datos->>'razon' as razon,
  datos as detalles
FROM event_log
WHERE usuario_id = 'user-456'
  AND tipo LIKE '%FALLO%'
  AND timestamp > NOW() - INTERVAL '1 day'
ORDER BY timestamp DESC;
```

### 3. Análisis de Eventos Problemáticos

```sql
SELECT 
  COUNT(*) as total_fallos,
  datos->>'paso_fallo' as paso,
  COUNT(CASE WHEN timestamp > NOW() - INTERVAL '1 hour' THEN 1 END) as fallos_ultima_hora
FROM event_log
WHERE evento_id = 'evt-concierto-2026'
  AND tipo = 'RESERVA_FALLIDA'
GROUP BY paso
ORDER BY total_fallos DESC;
```

### 4. GDPR: Modificaciones a Datos Personales

```sql
SELECT 
  timestamp,
  datos->>'campos_modificados' as campos,
  datos->>'valor_anterior' as antes,
  datos->>'valor_nuevo' as ahora
FROM event_log
WHERE usuario_id = 'user-456'
  AND tipo = 'DATOS_PERSONALES_MODIFICADOS'
ORDER BY timestamp;
```

### 5. Exportación de Datos (GDPR)

```sql
-- Ver todas las acciones del usuario
SELECT 
  timestamp,
  tipo,
  datos
FROM event_log
WHERE usuario_id = 'user-456'
ORDER BY timestamp
-- Resultado: auditoría completa para GDPR report
```

---

## Retention Policy

| Tipo de Evento | Retention | Razón |
|----------------|-----------|-------|
| RESERVA_* | 2 años | Legal |
| PAGO_* | 7 años | Compliance financiero |
| DATOS_PERSONALES_MODIFICADOS | Indefinido | GDPR |
| Otros | 1 año | Optimización |

---

## Performance

### Indexes Críticos

```sql
-- Búsquedas por usuario (auditoría)
CREATE INDEX ON event_log (usuario_id, timestamp DESC);

-- Búsquedas por tipo (análisis de fallos)
CREATE INDEX ON event_log (tipo, timestamp DESC);

-- Búsquedas recientes (operacional)
CREATE INDEX ON event_log (timestamp DESC) WHERE timestamp > NOW() - INTERVAL '90 days';
```

### Partition (para tablas muy grandes)

```sql
-- Si >100M registros, particionar por rango de timestamp
CREATE TABLE event_log_2026_09 PARTITION OF event_log
  FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
```

---

## Integridad de Datos

### Chain Integrity (como blockchain)

```sql
-- Verificar cadena no fue modificada
SELECT 
  id,
  hash_anterior,
  LAG(evento_id) OVER (ORDER BY id) as evento_anterior_esperado,
  CASE 
    WHEN hash_anterior = LAG(evento_id) OVER (ORDER BY id) 
    THEN 'OK' 
    ELSE 'CORROMPIDO' 
  END as integridad
FROM event_log
WHERE usuario_id = 'user-456'
ORDER BY id;
```

---

## Próximos Pasos

- [ ] Script SQL para crear tablas
- [ ] Política de archivado (older events → archive table)
- [ ] Encryption de campos sensibles
- [ ] Backup automático (WAL archiving)
