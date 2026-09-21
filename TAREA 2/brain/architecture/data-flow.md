---
name: data-flow
description: Flujo de datos entre microservicios EventFlow
metadata:
  type: architecture
  status: complete
---

# Flujo de Datos — EventFlow

## Flujo Principal: Compra de Entrada (SAGA)

```mermaid
sequenceDiagram
    participant Client
    participant RS as Reservas Service<br/>(Orquestador)
    participant US as Usuarios Service
    participant ES as Eventos Service
    participant Redis
    participant MongoDB
    participant PG as PostgreSQL

    Client->>RS: POST /api/reservar\n{usuario_id, evento_id, cantidad, metodo_pago}
    
    Note over RS: Chain of Responsibility\n1. ValidadorDeDatos\n2. ValidadorInventario\n3. ProcesadorPago\n4. ConfirmadorReserva\n5. Auditor

    RS->>US: GET /api/usuarios/{usuario_id}
    US-->>RS: 200 OK / 404
    
    RS->>ES: GET /api/eventos/{evento_id}
    ES-->>RS: 200 OK {entradas_disponibles} / 404
    
    Note over RS,Redis: Paso atómico en Redis (Lua Script)
    RS->>Redis: EVAL lua_pago_inventario\n{usuario_id, evento_id, cantidad, precio}
    Redis-->>RS: {pago_ok, inventario_ok}
    
    alt Éxito
        RS->>MongoDB: INSERT reserva
        RS->>PG: INSERT audit_event (SAGA_COMPLETED)
        RS-->>Client: 201 {reserva_id, estado: "confirmada", numero_confirmacion}
    else Fallo
        RS->>Redis: COMPENSACIÓN (rollback pago/inventario)
        RS->>PG: INSERT audit_event (SAGA_FAILED + compensaciones)
        RS-->>Client: 400/409/500 {error, detalle}
    end
```

---

## Flujo: Lectura de Usuario

```mermaid
sequenceDiagram
    participant Client
    participant US as Usuarios Service
    participant MongoDB

    Client->>US: GET /api/usuarios/{id}
    US->>MongoDB: findOne({_id: id})
    MongoDB-->>US: Documento usuario + historial_compras[]
    US-->>Client: 200 {usuario_id, nombre, email, historial_compras[]}
```

---

## Flujo: Lectura de Evento

```mermaid
sequenceDiagram
    participant Client
    participant ES as Eventos Service
    participant MongoDB

    Client->>ES: GET /api/eventos/{id}
    ES->>MongoDB: findOne({_id: id})
    MongoDB-->>ES: Documento evento
    ES-->>Client: 200 {evento_id, nombre, fecha, aforo_total, entradas_disponibles}
```

---

## Flujo: Exportación Anonimizada (GDPR)

```mermaid
sequenceDiagram
    participant Client
    participant US as Usuarios Service
    participant MongoDB

    Client->>US: GET /api/usuarios/exportar?format=json
    US->>MongoDB: find({}, {projection: {historial_compras: 1}})
    MongoDB-->>US: Cursor usuarios
    
    Note over US: Anonimización irreversible:\n- SHA-256(usuario_id + salt) → usuario_hash\n- Eliminar: nombre, apellido, email, nro_documento\n- Preservar: eventos_comprados, gasto_total
    
    US-->>Client: 200 {usuarios_anonimizados: [{usuario_hash, eventos_comprados, gasto_total}]}
```

---

## Flujo: Escritura de Evento (Audit Log)

```mermaid
sequenceDiagram
    participant RS as Reservas Service
    participant PG as PostgreSQL

    RS->>PG: INSERT INTO event_log\n(event_type, aggregate_id, payload, metadata, timestamp)
    
    Note over RS,PG: Eventos almacenados:\n- SAGA_STARTED\n- USUARIO_VALIDADO\n- EVENTO_VALIDADO\n- PAGO_PROCESADO\n- INVENTARIO_DECREMENTADO\n- RESERVA_CONFIRMADA\n- SAGA_COMPLETED\n- SAGA_FAILED\n- COMPENSACION_EJECUTADA
```

---

## Resumen de Flujos por Consistencia

| Flujo | Consistencia | Latencia Objetivo | Patrón |
|-------|--------------|-------------------|--------|
| Lectura Usuario | Eventual | < 50ms | Direct MongoDB |
| Lectura Evento | Eventual | < 50ms | Direct MongoDB |
| Listar Usuarios | Eventual | < 100ms | Paginado MongoDB |
| Compra Entrada | **Fuerte** | < 500ms | SAGA + Redis Lua |
| Exportar Anonimizado | Eventual | < 2s | Batch + Hash |

---

## Datos que Fluyen Entre Servicios

| Origen → Destino | Datos | Frecuencia |
|------------------|-------|------------|
| Reservas → Usuarios | `usuario_id` (validación) | Por reserva |
| Reservas → Eventos | `evento_id`, `cantidad` (validación + decremento) | Por reserva |
| Reservas → Redis | `pago_data`, `inventario_delta` | Por reserva (atómico) |
| Reservas → MongoDB | `reserva_document` | Por reserva exitosa |
| Reservas → PostgreSQL | `audit_event` | Por paso SAGA |

---

## Consideraciones de Rendimiento

1. **Lecturas paralelas**: Usuarios y Eventos se validan en paralelo en SAGA
2. **Redis Lua**: Pago + inventario en una sola operación atómica (single round-trip)
3. **Índices MongoDB**: 
   - `usuarios`: `_id`, `email` (unique), `nro_documento` (unique)
   - `eventos`: `_id`, `fecha`
   - `reservas`: `usuario_id`, `evento_id`, `estado`
4. **Connection pooling**: httpx.AsyncClient con límites