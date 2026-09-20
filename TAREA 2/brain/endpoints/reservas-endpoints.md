---
name: reservas-endpoints
description: Endpoints para Servicio de Reservas y Pagos
metadata:
  type: specification
  status: in-progress
---

# Endpoints — Servicio de Reservas y Pagos

## POST /api/reservar

Inicia el proceso de compra de entradas (SAGA + Chain of Responsibility).

**Request:**
```json
{
  "usuario_id": "65a1b2c3d4e5f6g7h8i9j0k1",
  "evento_id": "65a1b2c3d4e5f6g7h8i9j0k2",
  "cantidad": 2,
  "metodo_pago": "tarjeta_credito",
  "datos_pago": {
    "numero_tarjeta": "4532xxxxxxxxxxxx",
    "nombre_titular": "Juan Pérez",
    "cvv": "123",
    "fecha_expiracion": "12/28"
  }
}
```

**Response (201) — Éxito:**
```json
{
  "reserva_id": "res_65a1b2c3d4e5f6g7h8i9j0k3",
  "usuario_id": "65a1b2c3d4e5f6g7h8i9j0k1",
  "evento_id": "65a1b2c3d4e5f6g7h8i9j0k2",
  "cantidad": 2,
  "precio_total": 300.00,
  "estado": "confirmada",
  "confirmado_en": "2026-09-20T10:05:30Z",
  "numero_confirmacion": "CONF-2026092010053012345"
}
```

**Response (400) — Validación fallida:**
```json
{
  "error": "validacion_fallida",
  "detalles": "Usuario no encontrado"
}
```

**Response (409) — Inventario agotado:**
```json
{
  "error": "inventario_insuficiente",
  "disponibles": 1,
  "solicitadas": 2
}
```

**Response (500) — Fallo de pago (compensación iniciada):**
```json
{
  "error": "transaccion_fallida",
  "mensaje": "El pago fue rechazado. Se revertieron los cambios.",
  "detalles": "Transacción rollback completada"
}
```

---

## Flujo Interno (Chain of Responsibility + SAGA)

```
1. ValidadorDatos → verifica campos obligatorios
2. ValidadorInventario → verifica aforo disponible
3. ProcesadorDePago → procesa pago en Redis (atomic)
4. ConfirmadorTransaccion → registra en MongoDB

Si algún paso falla:
  → Compensaciones activan (revertir pago, liberar inventario)
  → Error 500 al cliente
```

---

## Garantías

- **Atomicidad:** Redis Lua scripts garantizan transacción atómica
- **Consistencia:** Sin dobles ventas
- **Idempotencia:** Si el cliente reintenta con mismo payload, devuelve resultado anterior (si existe)

---

## Tiempos de Respuesta

- **Esperado:** < 500ms (Redis + validaciones rápidas)
- **Timeout:** 5 segundos (fallback a error)
