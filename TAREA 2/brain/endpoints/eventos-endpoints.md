---
name: eventos-endpoints
description: Endpoints para Servicio de Eventos
metadata:
  type: specification
  status: draft
---

# Endpoints — Servicio de Eventos

## POST /api/eventos

Crea un nuevo evento.

```json
{
  "nombre": "Concierto de Rock 2026",
  "fecha": "2026-12-15T20:00:00Z",
  "lugar": "Estadio Nacional",
  "aforo_total": 50000,
  "precio_entrada": 150.00
}
```

**Response (201):**
```json
{
  "evento_id": "65a1b2c3d4e5f6g7h8i9j0k1",
  "nombre": "Concierto de Rock 2026",
  "aforo_total": 50000,
  "entradas_disponibles": 50000,
  "creado_en": "2026-09-20T10:00:00Z"
}
```

---

## GET /api/eventos/{evento_id}

Recupera información del evento y aforo disponible.

**Response (200):**
```json
{
  "evento_id": "65a1b2c3d4e5f6g7h8i9j0k1",
  "nombre": "Concierto de Rock 2026",
  "fecha": "2026-12-15T20:00:00Z",
  "lugar": "Estadio Nacional",
  "aforo_total": 50000,
  "entradas_vendidas": 12345,
  "entradas_disponibles": 37655,
  "precio_entrada": 150.00
}
```

---

## POST /api/eventos/{evento_id}/decrement-tickets

**(Uso interno — Reservas Service SAGA)**

Decrementa el inventario de entradas disponibles (operación atómica).

```json
{
  "cantidad": 2
}
```

**Response (200):**
```json
{
  "evento_id": "65a1b2c3d4e5f6g7h8i9j0k1",
  "entradas_disponibles": 37653
}
```

---

## Errores

- **400:** Datos inválidos
- **404:** Evento no encontrado
- **409:** No hay entradas disponibles
