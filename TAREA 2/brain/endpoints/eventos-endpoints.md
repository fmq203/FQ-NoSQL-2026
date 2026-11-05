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

Revisado contra el código: 2026-11-05 (`eventos-service/src/api/routes/eventos.py`).

---

## Endpoints

| Método | Ruta | Descripción | Consistencia |
|--------|------|-------------|--------------|
| GET | `/health` | Health check (MongoDB) | — |
| GET | `/metrics` | Métricas Prometheus | — |
| POST | `/api/eventos` | Crear evento | Fuerte (`w=majority`) |
| GET | `/api/eventos/{evento_id}` | Obtener evento (caché AP) | Eventual |
| POST | `/api/eventos/{evento_id}/decrementar-inventario` | Descontar entradas de una categoría (paso 4 de la SAGA) | Fuerte (operación atómica) |
| POST | `/api/eventos/{evento_id}/incrementar-inventario` | Devolver entradas (compensación del paso 5) | Fuerte |

No hay listado (`GET /api/eventos`), ni `PUT`/`PATCH`/`DELETE`. Si MongoDB no responde (y no hay caché que servir) se devuelve **503** con `Retry-After: 5`.

---

## Referencia Rápida

### POST /api/eventos

**Request Body** (`EventoCreate`):
```json
{
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",
  "fecha": "2026-12-15T20:00:00Z",
  "aforo_total": 100,
  "entradas_disponibles": 100,
  "precios": [
    {"categoria": "vip", "precio": 20000.00, "disponibles": 20},
    {"categoria": "general", "precio": 5000.00, "disponibles": 80}
  ],
  "ubicacion": {"ciudad": "Buenos Aires", "pais": "Argentina", "direccion": "Av. Siempre Viva 123"}
}
```

**Response 201** (`EventoResponse`): el mismo cuerpo más `evento_id`, `creado_en`, `actualizado_en` (con `fecha` normalizada a UTC).

**Validaciones (422, RFC 7807)**:
- `fecha` ISO 8601 entre 1970 y 2100 (sin zona se toma UTC)
- `entradas_disponibles ≤ aforo_total`
- `sum(precios[].disponibles) ≤ entradas_disponibles`
- Categorías únicas en `precios[]`; `precio ≥ 0` con 2 decimales como máximo
- `estado` ∈ `borrador`, `publicado`, `cancelado`, `finalizado`

**409**: ya existe un evento con ese `nombre`.

No se valida que la fecha sea futura.

---

### GET /api/eventos/{evento_id}

**Response 200** (`EventoResponse`): evento completo con `precios[].disponibles` y `entradas_disponibles`.

**Caché AP** (`services/lectura_cache.py`, Redis DB 1, clave `cache:evento:{id}`): header `X-Cache` = `HIT` (< 30 s), `MISS`, `STALE` (MongoDB caído, copia vencida de hasta 1 h) o `BYPASS` (`Cache-Control: no-cache`, lo manda la SAGA). Los 404 no se cachean.

**Errores**: 404 no existe; 422 UUID inválido; 503 MongoDB no disponible sin copia en caché.

---

### POST /api/eventos/{evento_id}/decrementar-inventario · /incrementar-inventario

**Request Body** (`AjusteInventarioRequest`):
```json
{"categoria": "general", "cantidad": 2}
```

**Response 200** (`AjusteInventarioResponse`):
```json
{"evento_id": "uuid", "categoria": "general", "disponibles": 78, "entradas_disponibles": 98}
```

Una sola operación atómica sobre el documento (`find_one_and_update` con `$elemMatch` + `$inc` sobre la categoría y el total). Al decrementar exige stock suficiente en la categoría.

**Errores**: 404 evento inexistente; 422 categoría inexistente o cantidad ≤ 0; 409 stock insuficiente (solo al decrementar). Ambos invalidan la caché del evento.

---

## Modelos Pydantic (Referencia)

Ver [[event-schema]] para las definiciones completas.

- `PrecioCategoria` - categoria, precio (Decimal), disponibles
- `Ubicacion` - ciudad, pais, direccion (opcional)
- `EventoCreate` - Request POST
- `EventoResponse` - Response
- `AjusteInventarioRequest` / `AjusteInventarioResponse` - Inventario
- `EstadoEvento` - Enum: borrador, publicado, cancelado, finalizado

---

## Especificación Completa

```bash
curl http://localhost:8002/openapi.json | jq '.paths'
curl http://localhost:8002/openapi.json | jq '.components.schemas'
```

---

## Referencias Relacionadas

- [[eventos]] - Spec completa servicio
- [[event-schema]] - Modelo de datos MongoDB
- [[saga-flow]] - Uso en los pasos 3 a 5 de la SAGA
- [[consistency-strategy]] - Consistencia eventual en lecturas
