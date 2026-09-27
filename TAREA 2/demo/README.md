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

1. **Diagrama de infraestructura** (estático): los 3 servicios, sus puertos, y su base de datos propia (database-per-service) — Mongo x2, Redis + PostgreSQL en Reservas.
2. **Estado en vivo** de los 3 servicios (`/health`, con sus `checks` por dependencia — Mongo/Redis/PostgreSQL/circuit breakers).
3. **Pipeline visual** de la SAGA (Chain of Responsibility, 6 pasos) que se anima al reservar.
4. **Crear usuario** → `POST /api/usuarios`.
5. **Crear evento** → `POST /api/eventos`.
6. **Reservar** → `POST /api/reservar` (usuario_id/evento_id se autocompletan de los pasos anteriores).
7. **Reintentar con el mismo `reserva_id`** → demuestra idempotencia (200, no 201, sin doble cobro).
8. **Botón de error real** → dispara una reserva con `evento_id` inexistente y muestra el RFC 7807 completo (`EVENT_NOT_FOUND`, 404).
9. **Escenarios de un click** → 8 botones, cada uno auto-contenido (crea su propio usuario/evento, sin tocar los formularios de arriba) y anima el pipeline marcando exactamente en qué paso ocurre el resultado:

   | Escenario | Resultado esperado | Falla en el paso |
   |-----------|---------------------|-------------------|
   | ✅ Camino feliz | 201 Created, reserva confirmada | — |
   | ❌ Usuario inexistente | 404 `USER_NOT_FOUND` | Validar Usuario |
   | ❌ Evento inexistente | 404 `EVENT_NOT_FOUND` | Validar Evento |
   | ❌ Evento no publicado | 409 `EVENT_NOT_AVAILABLE` (evento en `borrador`) | Validar Evento |
   | ❌ Inventario insuficiente | 409 `INSUFFICIENT_INVENTORY` (se pide más de lo disponible) | Validar Evento |
   | ❌ Categoría inexistente | 422 `VALIDATION_ERROR` (la categoría pedida no existe en el evento) | Validar Evento |
   | ❌ Cantidad inválida | 422 `VALIDATION_ERROR` (`cantidad=0`, rechazada por Pydantic antes de arrancar la SAGA) | Validar Datos |
   | 🔄 **Falla a mitad de camino (compensación real)** | 503 `SERVICE_UNAVAILABLE` — Redis ya cobró y decrementó inventario cuando la sincronización con Eventos Service falla; se compensa y el aforo del evento vuelve exactamente a como estaba | Procesar Pago |

   Todos se probaron de punta a punta contra el stack real (`node` simulando el mismo flujo del navegador) antes de darlos por buenos — ver `brain/learnings/learnings.md`.

10. **Auditoría PostgreSQL (event_log)**, al pie de la página → consulta `GET /api/reservar/{reserva_id}/audit` (nuevo endpoint, expone `get_events_by_aggregate()` que ya existía en el código pero no estaba conectado a ninguna ruta) y muestra la timeline completa de eventos de Event Sourcing para una reserva, incluidas las que fallaron y se compensaron. El campo se autocompleta solo con el último `reserva_id` usado en cualquier botón de arriba.

Las URLs base (por si corrés los servicios en otros puertos) son editables arriba de la página.

### Sobre el escenario de compensación real

Lograr que la SAGA falle *específicamente* después de que Redis ya mutó algo (y no antes, en la validación) requiere que eventos-service se caiga en una ventana de milisegundos entre el paso 3 (Validar Evento, que también llama a eventos-service) y el paso 4 (la sincronización posterior) — imposible de reproducir con un `docker stop` manual durante una demo en vivo. Por eso `POST /api/reservar` acepta un query param de solo-demo, `?simular_fallo=sync_pago`, que fuerza ese punto de fallo exacto de forma determinística. **El código de compensación que corre es exactamente el mismo que ante una caída real** (revierte Redis, emite `COMPENSACION_EJECUTADA` en el audit log) — lo único sintético es el disparador, no la respuesta del sistema. Está documentado en el propio código (`ReservaContext.simular_fallo_sync`) y cubierto por tests (`tests/integration/test_fault_injection_demo.py`).

## Qué NO muestra

El `saga_log` paso a paso en tiempo real (qué handler exacto corrió, con qué timing, dentro de una única request) no se expone por `POST /api/reservar` — esa respuesta es solo `{reserva_id, estado, numero_confirmacion}` (o el error RFC 7807). El pipeline animado es una visualización didáctica de la arquitectura, no un log en vivo de esa request puntual — para eso está la sección de Auditoría PostgreSQL, que sí muestra el historial real (aunque post-hoc, no mientras la request está en vuelo).
