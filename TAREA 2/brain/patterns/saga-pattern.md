---
name: saga-pattern
description: Implementación del patrón SAGA con Orquestación para Reservas
metadata:
  type: pattern
  status: in-progress
---

# Patrón SAGA — Orquestación

## Objetivo

Garantizar consistencia en una transacción distribuida (compra de entrada) que involucra múltiples microservicios y bases de datos.

---

## Arquitectura: Orquestador Central

```
┌──────────────────────────────┐
│ Reservas Service (Orch)      │
│ - Coordina los pasos         │
│ - Maneja compensaciones      │
└──────────┬───────────────────┘
           │
     ┌─────┴──────────────────────────────┐
     │                                    │
     ▼                                    ▼
┌─────────────────┐             ┌──────────────────┐
│ Usuarios Service│             │ Eventos Service  │
│ (Validación)    │             │ (Inventario)     │
└─────────────────┘             └──────────────────┘
                                         │
                                         ▼
                                  ┌──────────────────┐
                                  │ Redis (Pagos)    │
                                  │ (Atomic Txn)     │
                                  └──────────────────┘
```

---

## Flujo de Transacción Exitosa

```
POST /api/reservar
  │
  ├─ SAGA Step 1: Validar Usuario
  │  └─ GET /usuarios/{usuario_id} ✅
  │
  ├─ SAGA Step 2: Validar Evento + Inventario
  │  └─ GET /eventos/{evento_id} (entradas disponibles) ✅
  │
  ├─ SAGA Step 3: Procesar Pago (Redis Atomic)
  │  └─ Redis Lua Script: transferencia de fondos ✅
  │
  ├─ SAGA Step 4: Decrementar Inventario
  │  └─ POST /eventos/{evento_id}/decrement-tickets ✅
  │
  └─ SAGA Step 5: Registrar en MongoDB
     └─ Crear documento de reserva confirmada ✅

Result: 201 Created { reserva_id, confirmacion, ... }
```

---

## Flujo de Compensación (Fallo en Step 3 - Pago)

```
POST /api/reservar
  │
  ├─ Step 1: Validar Usuario ✅
  ├─ Step 2: Validar Evento ✅
  ├─ Step 3: Procesar Pago ❌ FALLO
  │
  └─ COMPENSACIONES (Rollback):
     │
     ├─ Compensación Step 3: Revertir Pago (Crédito)
     │  └─ Redis: liberar fondos bloqueados ✅
     │
     └─ Fin: Error 500 al cliente

Result: 500 Error { "transaccion_fallida": true }
```

---

## Flujo de Compensación (Fallo en Step 4 - Inventario)

```
POST /api/reservar
  │
  ├─ Step 1: Validar Usuario ✅
  ├─ Step 2: Validar Evento ✅
  ├─ Step 3: Procesar Pago ✅
  ├─ Step 4: Decrementar Inventario ❌ FALLO (race condition)
  │
  └─ COMPENSACIONES:
     │
     ├─ Compensación Step 3: Revertir Pago
     │  └─ Redis: crédito al usuario ✅
     │
     └─ Fin: Error 500, cliente reintenta

Result: 500 Error { "inventario_race_condition": true }
```

---

## Implementación: Pseudocódigo

```python
class ReservasOrchestrator:
    def procesar_reserva(self, solicitud):
        try:
            # Step 1
            usuario = self.usuarios_service.get(solicitud.usuario_id)
            if not usuario:
                raise ValidationError("Usuario no existe")
            
            # Step 2
            evento = self.eventos_service.get(solicitud.evento_id)
            if evento.entradas_disponibles < solicitud.cantidad:
                raise ValidationError("Inventario insuficiente")
            
            # Step 3 (ATÓMICO en Redis)
            pago = self.redis.execute_lua_script(
                script=PROCESAR_PAGO_SCRIPT,
                args=[
                    solicitud.usuario_id,
                    solicitud.evento_id,
                    solicitud.cantidad,
                    evento.precio
                ]
            )
            
            if not pago['ok']:
                raise PaymentError(pago['err'])
            
            # Step 4
            evento_actualizado = self.eventos_service.decrement_tickets(
                solicitud.evento_id,
                solicitud.cantidad
            )
            
            # Step 5
            reserva = self.mongodb.reservas.insert_one({
                'usuario_id': solicitud.usuario_id,
                'evento_id': solicitud.evento_id,
                'cantidad': solicitud.cantidad,
                'estado': 'confirmada'
            })
            
            return { 'reserva_id': reserva.id, 'estado': 'confirmada' }
        
        except Exception as e:
            # COMPENSACIONES
            self.compensar(solicitud, e)
            raise SagaFailure("Transacción fallida", detalles=str(e))
    
    def compensar(self, solicitud, error):
        # Revertir pago (Step 3)
        self.redis.revertir_pago(solicitud.usuario_id)
        # Liberar inventario (si ya se decrementó)
        self.eventos_service.increment_tickets(solicitud.evento_id, solicitud.cantidad)
```

---

## Garantías

| Garantía | SAGA Orchestration |
|----------|-------------------|
| Atomicidad | ⚠️ No garantizada (es distribuida) |
| Consistencia | ✅ Eventual (con compensaciones) |
| Isolation | ⚠️ Limitada (pueden haber reads dirty) |
| Durabilidad | ✅ MongoDB + Redis persistence |

---

## Comparación: SAGA vs Transacción Tradicional

| Aspecto | SAGA | Transacción SQL |
|--------|------|-----------------|
| Coordinación | Orquestador explícito | DBMS automatiza |
| Microservicios | ✅ Soporta | ❌ No (BD única) |
| Consistencia | Eventual + compensaciones | Strong ACID |
| Complejidad | Alta | Media |

---

## Casos de Uso en EventFlow

- **Compra de Entrada:** SAGA principal
- **Cancelación:** SAGA inversa (compensación)
- **Reembolso:** SAGA parcial

---

## Próximos Pasos

- [ ] Implementar Lua script de pagos
- [ ] Testing de compensaciones
- [ ] Monitoring de SAGA states
- [ ] Documentar timeouts y retries
