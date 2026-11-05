---
name: docker-setup
description: Configuración Docker para cada microservicio
metadata:
  type: deployment
  status: complete
---

# Docker Setup - Configuración por Servicio

**Última revisión contra el código:** 2026-11-05

## Estructura

```
usuarios-service/   eventos-service/   reservas-service/
├── Dockerfile      ├── Dockerfile     ├── Dockerfile
├── requirements.txt├── requirements.txt├── requirements.txt
├── pytest.ini      ├── pytest.ini     ├── pytest.ini
├── src/            ├── src/           ├── src/
└── tests/          └── tests/         └── tests/
```

---

## Dockerfile (igual en los tres; cambia el puerto: 8001 / 8002 / 8003)

```dockerfile
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8001}/health || exit 1

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-8001}"]
```

- Se copia **solo `src/`**: los tests no van en la imagen. `make test` corre cada suite dentro de su contenedor montando `tests/`, `pytest.ini` y el `Dockerfile` en modo lectura (`docker compose exec <svc> pytest` sin montarlos no encuentra tests).
- La app se importa como `src.main:app`.
- `curl` es para el health check; `gcc` para compilar dependencias nativas.

Variables de entorno por servicio: ver [[docker-compose]].

---

## Dependencias principales (`requirements.txt`)

| | usuarios | eventos | reservas |
|---|---|---|---|
| Web | fastapi 0.109, uvicorn[standard] 0.27, pydantic 2.5 + settings | ídem | ídem |
| MongoDB | motor 3.3.2, pymongo 4.6.1 | ídem | ídem |
| Redis | redis 5.0 (caché) | redis 5.0 (caché) | redis 5.0 (Lua) |
| PostgreSQL | (asyncpg, psycopg, sqlalchemy listados pero no usados) | — | asyncpg 0.29 |
| HTTP | httpx | httpx | httpx (clientes hacia Usuarios/Eventos), requests (tests) |
| Métricas | prometheus-client 0.19 | ídem | ídem |
| Tests | pytest 7.4, pytest-asyncio, fakeredis 2.20 (testcontainers listado, no usado) | pytest, fakeredis, **schemathesis 3.39.16**, pytest-cov | pytest, fakeredis, pyflakes |

Las dependencias de test van en la misma `requirements.txt` (por eso `make test` puede correr dentro de la imagen del servicio).

---

## Build y Run

```bash
make up                                   # build + up de todo
docker compose build reservas-service     # rebuild de uno
docker compose up -d reservas-service
```

Correr un servicio suelto (fuera de compose) requiere apuntar sus variables a las bases:

```bash
docker build -t eventflow-usuarios ./usuarios-service
docker run -d -p 8001:8001 -e MONGODB_URI=mongodb://host.docker.internal:27017 eventflow-usuarios
```

---

## Mejoras no implementadas

- Build multi-stage (imagen final sin `gcc`).
- Separar dependencias de test (`requirements-dev.txt`).
- Usuario no root en la imagen.

---

## Referencias

- [[docker-compose]] - docker-compose.yml real y variables
- [[deployment-checklist]] - Checklist
- [[deployment-strategy]] - Estrategia completa
