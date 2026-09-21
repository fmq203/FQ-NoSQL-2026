---
name: eventos-endpoints
description: Referencia a endpoints de Eventos Service (OpenAPI auto-generado)
metadata:
  type: specification
  status: complete
---

# Endpoints: Eventos Service

## Fuente de Verdad

**OpenAPI Spec auto-generado por FastAPI**: http://localhost:8002/openapi.json  
**Swagger UI**: http://localhost:8002/docs  
**ReDoc**: http://localhost:8002/redoc

---

## Endpoints

| Método | Ruta | Descripción | Consistencia |
|--------|------|-------------|--------------|
| GET | `/health` | Health check | — |
| POST | `/api/eventos` | Crear evento | Fuerte |
| GET | `/api/eventos/{evento_id}` | Obtener evento + aforo | Eventual |

---

## Referencia Rápida

### POST /api/eventos

**Request Body** (`EventoCreate`):
```json
{
  "nombre": "Concierto Rock 2026",
  "descripcion": "Gran festival de rock",
  "fecha": "2026-12-15T20:00:00Z",
  "ubicacion": {
    "venue": "Estadio Central",
    "direccion": "Av. Principal 123",
    "ciudad": "Madrid",
    "pais": "España",
    "coordenadas": {"lat": 40.4168, "lng": -3.7038}
  },
  "aforo_total": 50000,
  "precios": [
    {"categoria": "VIP", "precio": 200.0, "disponibles": 1000},
    {"categoria": "General", "precio": 80.0, "disponibles": 30000},
    {"categoria": "Popular", "precio": 40.0, "disponibles": 19000}
  ],
  "categorias": ["musica", "rock", "festival"]
}
```

**Response 201** (`Evento`):
```json
{
  "evento_id": "550e8400-e29b-41d4-a716-446655440001",
  "nombre": "Concierto Rock 2026",
  "fecha": "2026-12-15T20:00:00Z",
  "aforo_total": 50000,
  "entradas_disponibles": 50000,
  "estado": "borrador"
}
```

**Validaciones (422)**:
- Fecha debe ser futura
- Aforo > 0
- Suma precios[].disponibles <= aforo_total
- Categorías únicas en precios[]

---

### GET /api/eventos/{evento_id}

**Path Parameter**: `evento_id` (UUID)

**Response 200** (`Evento`): Evento completo con `entradas_disponibles` actualizado

**Cache**: Redis cache-aside (TTL 30s) para `entradas_disponibles`

**Errores**:
- 404: Evento no encontrado
- 422: UUID inválido

---

## Modelos Pydantic (Referencia)

Ver `brain/data-models/event-schema.md` para definiciones completas.

- `PrecioCategoria` - categoría, precio, disponibles
- `Ubicacion` - venue, direccion, ciudad, pais, coordenadas
- `EventoCreate` - Request POST
- `Evento` - Response con entradas_disponibles
- `EstadoEvento` - Enum: borrador, publicado, cancelado, finalizado

---

## Especificación Completa

```bash
curl http://localhost:8002/openapi.json | jq '.paths'
curl http://localhost:8002/openapi.json | jq '.components.schemas'
```

---

## Referencias Relacionadas

- [[microservices/eventos]] - Spec completa servicio
- [[data-models/event-schema]] - Modelo de datos MongoDB + Redis
- [[architecture/saga-flow]] - Uso en SAGA paso 3-4
- [[decisions/consistency-strategy]] - Consistencia eventual en lecturas