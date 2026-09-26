# Demo GUI — EventFlow

Página HTML estática (un solo archivo, sin build ni dependencias externas) que llama directo a las tres APIs vía `fetch()` desde el navegador. Sirve para mostrar el flujo completo (usuario → evento → reserva/SAGA) durante la defensa.

## Requisitos

Las tres APIs ya tienen CORS abierto (`allow_origins=["*"]`), así que el demo funciona apenas el stack esté arriba:

```bash
cd ".."  # raíz del repo (TAREA 2/)
docker compose up -d --build   # --build es importante: reconstruye con el código actual
```

`--build` importa porque las imágenes viejas no se reconstruyen solas al levantar el stack — si el código cambió y no se reconstruye, el demo va a mostrar comportamiento desactualizado (ej. códigos de error genéricos en vez de los específicos, sin retries/circuit breaker, etc.).

## Cómo abrirlo

Cualquiera de las dos funciona:

```bash
# Opción 1: servido (recomendado, evita cualquier restricción de origen file://)
cd demo
python3 -m http.server 8080
# abrir http://localhost:8080

# Opción 2: abrir el archivo directo
xdg-open index.html   # o doble click en el Finder/Explorador
```

## Qué muestra

1. **Estado en vivo** de los 3 servicios (`/health`, con sus `checks` por dependencia — Mongo/Redis/PostgreSQL/circuit breakers).
2. **Pipeline visual** de la SAGA (Chain of Responsibility, 6 pasos) que se anima al reservar.
3. **Crear usuario** → `POST /api/usuarios`.
4. **Crear evento** → `POST /api/eventos`.
5. **Reservar** → `POST /api/reservar` (usuario_id/evento_id se autocompletan de los pasos anteriores).
6. **Reintentar con el mismo `reserva_id`** → demuestra idempotencia (200, no 201, sin doble cobro).
7. **Botón de error real** → dispara una reserva con `evento_id` inexistente y muestra el RFC 7807 completo (`EVENT_NOT_FOUND`, 404).
8. **Escenarios de un click** → 7 botones, cada uno auto-contenido (crea su propio usuario/evento, sin tocar los formularios de arriba) y anima el pipeline marcando exactamente en qué paso ocurre el resultado:

   | Escenario | Resultado esperado | Falla en el paso |
   |-----------|---------------------|-------------------|
   | ✅ Camino feliz | 201 Created, reserva confirmada | — |
   | ❌ Usuario inexistente | 404 `USER_NOT_FOUND` | Validar Usuario |
   | ❌ Evento inexistente | 404 `EVENT_NOT_FOUND` | Validar Evento |
   | ❌ Evento no publicado | 409 `EVENT_NOT_AVAILABLE` (evento en `borrador`) | Validar Evento |
   | ❌ Inventario insuficiente | 409 `INSUFFICIENT_INVENTORY` (se pide más de lo disponible) | Validar Evento |
   | ❌ Categoría inexistente | 422 `VALIDATION_ERROR` (la categoría pedida no existe en el evento) | Validar Evento |
   | ❌ Cantidad inválida | 422 `VALIDATION_ERROR` (`cantidad=0`, rechazada por Pydantic antes de arrancar la SAGA) | Validar Datos |

   Los 7 se probaron de punta a punta contra el stack real (`node` simulando el mismo flujo del navegador) antes de darlos por buenos — ver `brain/learnings/learnings.md`.

Las URLs base (por si corrés los servicios en otros puertos) son editables arriba de la página.

## Qué NO muestra

El `saga_log` paso a paso (qué handler exacto corrió, con qué timing) no se expone por la API pública — `POST /api/reservar` devuelve solo `{reserva_id, estado, numero_confirmacion}` (o el error RFC 7807). El pipeline animado es una visualización didáctica de la arquitectura, no un log en vivo por request.
