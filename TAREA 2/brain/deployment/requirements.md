---
name: requirements
description: Requisitos para correr EventFlow y dependencias reales de cada servicio
metadata:
  type: specification
  status: complete
---

# Requisitos & Dependencias

**Revisado contra el código:** 2026-11-05. Reemplaza la versión de la etapa de diseño (que listaba paquetes y versiones que no se usaron, como un `spec-kit` de pip).

## Para correr el proyecto

| Herramienta | Uso |
|-------------|-----|
| Docker + Docker Compose v2 | Las 3 bases y los 3 servicios (`make up`) |
| GNU Make | `make up`, `make test`, `make jmeter`, `make logs` |
| Python 3 (host, solo stdlib) | `demo/servidor.py` (demo + botones de Docker) y `jmeter/resumen.py` |
| Navegador | Demo en http://localhost:8080/index.html |

No hace falta Python ni dependencias instaladas en el host para levantar ni testear: todo corre en contenedores (`python:3.11-slim`). JMeter también corre en Docker (`justb4/jmeter:5.5`, `--network host`, pensado para Linux/WSL2).

## Imágenes de bases de datos

| Base | Imagen | Notas |
|------|--------|-------|
| MongoDB | `mongo:7.0` | Un nodo, sin replica set |
| Redis | `redis:7.0-alpine` | `--appendonly yes`; DB 0 transacciones, DB 1 caché |
| PostgreSQL | `postgres:15-alpine` | `eventflow` / `eventflow_user`; el esquema lo crea Reservas al iniciar |

## Dependencias Python por servicio

Ver la tabla en [[docker-setup]]. Resumen: FastAPI 0.109 + uvicorn 0.27 + Pydantic 2.5, Motor 3.3 / PyMongo 4.6, redis-py 5.0, asyncpg 0.29 (Reservas), httpx 0.26, prometheus-client 0.19; tests con pytest 7.4, pytest-asyncio, fakeredis 2.20 y schemathesis 3.39.16 (Eventos). Las dependencias de test están en la misma `requirements.txt`.

**Ojo con versiones**: fakeredis 2.20 no funciona con redis-py 8 (falla con `unknown command HELLO`); por eso redis-py está fijo en 5.0.0.

## Variables de entorno

Valores por defecto en `docker-compose.yml` y ejemplo en `.env.example`. Las que importan:

```bash
EXPORT_PSEUDONYM_KEY=        # vacía: seudónimos efímeros (anonimización); con valor: estables
CACHE_REDIS_URL=redis://redis:6379/1
```

Detalle completo en [[docker-compose]].

## Inicio rápido

```bash
cd "TAREA 2"
make up                       # build + up, espera healthy
make test                     # 56 + 93 + 112 (+4 skipped)
python3 demo/servidor.py      # http://localhost:8080/index.html
```

## Problemas comunes

| Problema | Solución |
|----------|----------|
| `make test` corre 0 tests | Las imágenes no incluyen `tests/`; usar `make test` (los monta), no `docker compose exec <svc> pytest` |
| Puerto 8001-8003 / 27017 / 6379 / 5432 ocupado | Liberar el puerto o cambiar el mapeo en `docker-compose.yml` |
| Cambié código y no se ve | `make up` reconstruye (`--build`); un `docker compose up -d` solo no |
| MongoDB "Too many open files" tras muchas corridas de tests | `docker compose restart mongodb` |
| La demo dice "Control no disponible" | Servirla con `python3 demo/servidor.py`, no con `http.server` ni `file://` |
