---
name: event-log-pattern
description: Patrón Append-Only Event Log con PostgreSQL
metadata:
  type: pattern
  status: in-progress
---

# Patrón Event Log (Append-Only)

## Concepto

El **Event Log** es un registro inmutable de todos los eventos importantes del sistema. No es una base de datos "normal" — es una **cinta de auditoría** que solo crece (append-only).

```
Transacción 1 → evento_creado → ✅ Agregado al log
Transacción 2 → pago_procesado → ✅ Agregado al log
Transacción 3 → inventario_decrementado → ✅ Agregado al log

Nunca se modifica ni elimina (immutable).
Solo se agrega al final.
```

---

## Flujo: SAGA + Event Log

```
POST /api/reservar
    │
    ├─ SAGA Step 1: Validar
    │  └─ evento: RESERVA_INICIADA
    │     insertado en PostgreSQL ✅
    │
    ├─ SAGA Step 2: Validar inventario
    │  └─ evento: INVENTARIO_VALIDADO
    │     insertado en PostgreSQL ✅
    │
    ├─ SAGA Step 3: Procesar pago (Redis)
    │  ├─ éxito: evento: PAGO_PROCESADO ✅
    │  └─ fallo: evento: PAGO_RECHAZADO ❌
    │     insertado en PostgreSQL
    │
    ├─ SAGA Step 4: Decrement inventario (MongoDB)
    │  ├─ éxito: evento: INVENTARIO_DECREMENTADO ✅
    │  └─ fallo: evento: INVENTARIO_FALLO ❌
    │
    ├─ SAGA Step 5: Confirmar en MongoDB
    │  ├─ éxito: evento: RESERVA_CONFIRMADA ✅
    │  └─ fallo: evento: RESERVA_FALLIDA ❌
    │
    └─ Resultado final registrado en PostgreSQL
       (auditoría completa de qué pasó)

** IMPORTANTE **
- PostgreSQL registra incluso los FALLOS
- Si SAGA falla en Step 3, queda registrado:
  PAGO_RECHAZADO → RESERVA_FALLIDA
  (trazabilidad completa para debugging)
```

---

## Implementación: Pseudocódigo

```python
class EventLog:
    def __init__(self, postgresql_connection):
        self.db = postgresql_connection
    
    def registrar_evento(self, tipo, usuario_id, evento_id, datos, ip_address=None):
        """Registra un evento en el log (append-only)."""
        query = """
        INSERT INTO event_log 
          (tipo, usuario_id, evento_id, datos, ip_address, hash_anterior)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, timestamp;
        """
        
        # Obtener hash del evento anterior (para chain integrity)
        hash_anterior = self.obtener_ultimo_evento_id(usuario_id)
        
        resultado = self.db.execute(query, [
            tipo,
            usuario_id,
            evento_id,
            json.dumps(datos),  # JSONB
            ip_address,
            hash_anterior
        ])
        
        return resultado
    
    def obtener_ultimo_evento_id(self, usuario_id):
        """Obtiene el ID del último evento del usuario (para chain)."""
        query = """
        SELECT evento_id FROM event_log
        WHERE usuario_id = %s
        ORDER BY timestamp DESC LIMIT 1;
        """
        resultado = self.db.execute(query, [usuario_id])
        return resultado[0]['evento_id'] if resultado else None

# ============ EN SAGA ORCHESTRATOR ============

class ReservasOrchestrator:
    def __init__(self, redis, mongodb, postgresql):
        self.redis = redis
        self.mongodb = mongodb
        self.event_log = EventLog(postgresql)
    
    def procesar_reserva(self, solicitud):
        try:
            # Step 1: Validar usuario
            usuario = self.mongodb.usuarios.findOne({'_id': solicitud.usuario_id})
            if not usuario:
                # Registrar FALLO en PostgreSQL
                self.event_log.registrar_evento(
                    tipo='RESERVA_INICIADA',
                    usuario_id=solicitud.usuario_id,
                    evento_id=solicitud.evento_id,
                    datos={'paso_fallo': 1, 'razon': 'usuario_no_existe'},
                    ip_address=solicitud.ip
                )
                raise ValidationError("Usuario no existe")
            
            # ✅ Registrar evento exitoso
            self.event_log.registrar_evento(
                tipo='USUARIO_VALIDADO',
                usuario_id=solicitud.usuario_id,
                evento_id=solicitud.evento_id,
                datos={'usuario_nombre': usuario['nombre']}
            )
            
            # Step 2: Validar inventario
            evento = self.mongodb.eventos.findOne({'_id': solicitud.evento_id})
            if evento['entradas_disponibles'] < solicitud.cantidad:
                self.event_log.registrar_evento(
                    tipo='INVENTARIO_INSUFICIENTE',
                    usuario_id=solicitud.usuario_id,
                    evento_id=solicitud.evento_id,
                    datos={'disponibles': evento['entradas_disponibles']}
                )
                raise ValidationError("Inventario insuficiente")
            
            # ✅ Registrar
            self.event_log.registrar_evento(
                tipo='INVENTARIO_VALIDADO',
                usuario_id=solicitud.usuario_id,
                evento_id=solicitud.evento_id,
                datos={'cantidad_solicitada': solicitud.cantidad}
            )
            
            # Step 3: Procesar pago en Redis (atomic)
            pago_result = self.redis.execute_lua_script(PAGO_SCRIPT, solicitud)
            
            if not pago_result['ok']:
                # ❌ Registrar FALLO en PostgreSQL
                self.event_log.registrar_evento(
                    tipo='PAGO_RECHAZADO',
                    usuario_id=solicitud.usuario_id,
                    evento_id=solicitud.evento_id,
                    datos={'razon': pago_result['err']}
                )
                raise PaymentError(pago_result['err'])
            
            # ✅ Registrar pago exitoso
            self.event_log.registrar_evento(
                tipo='PAGO_PROCESADO',
                usuario_id=solicitud.usuario_id,
                evento_id=solicitud.evento_id,
                datos={
                    'pago_id': pago_result['pago_id'],
                    'monto': solicitud.monto
                }
            )
            
            # Step 4-5: Actualizar MongoDB y confirmar
            # ... (resto de SAGA steps)
            
            # ✅ ÉXITO: Registrar confirmación final
            self.event_log.registrar_evento(
                tipo='RESERVA_CONFIRMADA',
                usuario_id=solicitud.usuario_id,
                evento_id=solicitud.evento_id,
                datos={
                    'reserva_id': nueva_reserva.id,
                    'numero_confirmacion': nueva_reserva.confirmacion
                }
            )
            
            return {'status': 'éxito', 'reserva_id': nueva_reserva.id}
        
        except Exception as e:
            # ❌ Registrar FALLO general
            self.event_log.registrar_evento(
                tipo='RESERVA_FALLIDA',
                usuario_id=solicitud.usuario_id,
                evento_id=solicitud.evento_id,
                datos={
                    'razon': str(e),
                    'paso_fallo': self.detectar_paso_fallo(e)
                }
            )
            # Compensaciones...
            raise SagaFailure(str(e))
```

---

## Ventajas del Patrón

| Ventaja | Ejemplo |
|---------|---------|
| **Auditoría Completa** | Ver EXACTAMENTE qué pasó en cada paso |
| **Debugging** | "¿Por qué falló esta compra?" → buscar en event log |
| **Compliance GDPR** | Registro inmutable de accesos a datos personales |
| **Trazabilidad** | Chain of events con timestamps ordenados |
| **Replay** | Potencialmente reconstruir estado (Event Sourcing avanzado) |
| **Analytics** | SQL queries sobre eventos históricos |

---

## Queries Útiles para Debugging

### ¿Por qué falló la compra del usuario X?

```sql
SELECT timestamp, tipo, datos
FROM event_log
WHERE usuario_id = 'user-456'
  AND evento_id = 'evt-789'
ORDER BY timestamp;

-- Resultado:
-- 10:05:30 | USUARIO_VALIDADO | {...}
-- 10:05:31 | INVENTARIO_VALIDADO | {...}
-- 10:05:32 | PAGO_PROCESADO | {...}
-- 10:05:33 | INVENTARIO_DECREMENTADO | {...}
-- 10:05:34 | RESERVA_CONFIRMADA | {...}  ← Éxito

-- O si falló:
-- 10:05:30 | USUARIO_VALIDADO | {...}
-- 10:05:31 | PAGO_RECHAZADO | {"razon": "fondos insuficientes"}  ← FALLO
-- 10:05:31 | RESERVA_FALLIDA | {"paso_fallo": 3}
```

---

## Características de PostgreSQL Aprovechadas

| Característica | Uso |
|---------------|-----|
| **JSONB** | `datos` almacena cualquier estructura |
| **Timestamps** | `timestamp` garantiza orden (no confuso como en NoSQL) |
| **Indexes** | Búsquedas rápidas por usuario, tipo, timestamp |
| **Partitioning** | Para tablas enormes, particionar por mes/trimestre |
| **WAL (Write-Ahead Logging)** | Durabilidad garantizada |
| **ACID** | Garantía de que evento se escribió o no (no medio escrito) |

---

## Limitaciones & Mitigaciones

| Limitación | Mitigación |
|-----------|-----------|
| **Tabla crece indefinidamente** | Archivado a tabla histórica después de 1-2 años |
| **Búsquedas lentas en tabla gigante** | Partitioning por timestamp + indexes |
| **No es "real-time"** | PostgreSQL is fast pero no como Redis (< 1ms) |

---

## Próximos Pasos

- [ ] Implementar EventLog class en Python
- [ ] Agregar async writes (si volumen es muy alto)
- [ ] Crear vistas SQL para queries comunes
- [ ] Set up archivado automático de eventos viejos
- [ ] Dashboards de eventos (Grafana)
