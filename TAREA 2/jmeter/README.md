# Pruebas de carga con JMeter

Plan `eventflow.jmx` (JMeter 5.5), ejecutado en Docker: no hace falta instalar nada.

```bash
make up          # el stack tiene que estar arriba
make jmeter      # ~2 min; escribe en jmeter/results/<fecha>/ (no borra corridas anteriores)
```

Cada corrida deja `resultados.jtl` (crudo), `report/index.html` (dashboard de JMeter) y un resumen por consola (`resumen.py`).
`make jmeter` termina con error si alguna aserción falla o si se vendió una cantidad distinta del stock.

`--network host` es solo Linux. En Docker Desktop (Mac/Windows) hay que quitarlo y pasar `JMETER_ARGS="-Jhost=host.docker.internal"`.

## Qué prueba

| Grupo | Qué hace | Qué verifica |
|-------|----------|--------------|
| `setUp` | Crea 1 usuario y 1 evento con stock limitado (`stock`, default 50) | — |
| **1. Doble venta** | `dv_threads` (100) compradores × `dv_loops` (3) intentos contra **ese mismo evento** | Exactamente `stock` compras (201); el resto, 409. Nunca más ventas que stock |
| **2. Compra sostenida** | SAGA completa (`POST /api/reservar`) durante `compra_segundos` (30) con 20 hilos y un *Constant Throughput Timer* de 6000/min (= 100 req/s, RP-SC-007). Cada hilo crea su propio usuario y evento | 201 en todas las compras; latencias y tasa alcanzada |
| **3. Lecturas AP** | `GET /api/eventos/{id}` y `GET /api/usuarios/{id}` a máxima velocidad durante `lectura_segundos` (30) | 200; la mayoría sale del caché Redis |
| `tearDown` | Lee el evento de la doble venta **sin caché** (`Cache-Control: no-cache`) | `entradas_disponibles == 0` y `disponibles == 0`: no se vendió de más |

Parámetros (`-J<nombre>=<valor>`, vía `JMETER_ARGS`): `stock`, `dv_threads`, `dv_loops`, `compra_threads`, `compra_segundos`, `compra_por_minuto`, `lectura_threads`, `lectura_segundos`, `host`, `usuarios_port`, `eventos_port`, `reservas_port`.
Ejemplo: `make jmeter JMETER_ARGS="-Jcompra_segundos=60 -Jcompra_threads=40"`.

## Resultados medidos

Máquina de desarrollo (WSL2, 8 núcleos); JMeter, los tres servicios y las tres bases corren en la **misma** máquina, así que compiten por CPU. Servicios con la configuración por defecto (un proceso uvicorn cada uno).

**Doble venta** (300 intentos, stock 50): **50 compras (201) y 250 rechazos (409)**, inventario final 0. El script Lua de Redis y el `$elemMatch` de Eventos impiden vender de más aun con 100 compradores simultáneos. (Los 100 llegan a la vez, por eso la latencia de este grupo es alta —p99 ≈ 4 s— y no es representativa.)

**Lecturas** (20 hilos): `GET /api/eventos/{id}` ≈ 174 req/s (p99 ≈ 175 ms) y `GET /api/usuarios/{id}` ≈ 174 req/s (p99 ≈ 138 ms), sin errores.

**SAGA completa**, 20 hilos con límite de 100 req/s: se alcanzaron **≈ 31 req/s**, con latencia media 573 ms, p95 761 ms y p99 929 ms, sin errores.

**RP-SC-007 (p99 < 1 s a 100 req/s) no se cumple de punta a punta en esta máquina.** El techo medido de la SAGA completa es de unos 50 req/s:

| Hilos | req/s | p95 | p99 |
|------:|------:|----:|----:|
| 1 | 11.6 | 170 ms | 294 ms |
| 5 | 29.4 | 209 ms | 262 ms |
| 20 | 47.9 | 589 ms | 688 ms |
| 80 | 52.0 | 2073 ms | 2372 ms |

Una SAGA aislada tarda unos 100 ms (varias escrituras durables y ~4 llamadas HTTP entre servicios). El rendimiento se aplana en ≈ 50 req/s y de ahí en más solo crece la latencia. Hipótesis descartadas con una medición cada una:

- **CPU de Python:** con 4 workers de uvicorn en los tres servicios el resultado fue 46 req/s (sin mejora).
- **Commit sincrónico de PostgreSQL** (8 inserts de `event_log` por SAGA): con `synchronous_commit=off` dio 49 req/s (sin mejora).

El cuello de botella **no está identificado**. Sospechas sin comprobar: las escrituras con `w=majority` + `journal` en MongoDB, el `docker-proxy` de los puertos publicados en WSL2, o la propia máquina compartida con JMeter. Es una prueba de un solo nodo en una laptop; no se extrapola a otro hardware.

Para comparar: el test de `pytest` que pace 100 req/s (`reservas-service/tests/performance`) da p99 ≈ 175–335 ms, pero con Usuarios, Eventos y la mayoría de las dependencias **mockeadas**: mide la lógica del servicio, no el sistema completo. El número honesto de punta a punta es el de esta página.
