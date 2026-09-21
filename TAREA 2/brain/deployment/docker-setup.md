---
name: docker-setup
description: Configuración Docker para cada microservicio
metadata:
  type: deployment
  status: complete
---

# Docker Setup - Configuración por Servicio

## Estructura de Dockerfiles

```
usuarios-service/
├── Dockerfile
├── requirements.txt
└── src/

eventos-service/
├── Dockerfile
├── requirements.txt
└── src/

reservas-service/
├── Dockerfile
├── requirements.txt
└── src/
```

---

## Usuarios Service - Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar curl para healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY src/ .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Variables de Entorno**:
```bash
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
SERVICE_PORT=8001
ANONYMIZATION_SALT=eventflow-salt-2026-change-in-production
```

**Healthcheck**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

---

## Eventos Service - Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

**Variables de Entorno**:
```bash
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
REDIS_URL=redis://redis:6379
SERVICE_PORT=8002
```

**Healthcheck**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

---

## Reservas Service - Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

**Variables de Entorno**:
```bash
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
REDIS_URL=redis://redis:6379
POSTGRESQL_URI=postgresql://eventflow_user:eventflow_password@postgresql:5432/eventflow
USUARIOS_SERVICE_URL=http://usuarios-service:8001
EVENTOS_SERVICE_URL=http://eventos-service:8002
SERVICE_PORT=8003
```

**Healthcheck**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

---

## Requirements.txt Común (Base)

```txt
# Core
fastapi==0.104.0
uvicorn==0.24.0
pydantic>=2.0.0,<3.0.0
pydantic-extra-types==2.0.0
email-validator==2.1.0

# Databases
pymongo==4.5.0
redis==5.0.0
psycopg[binary]==3.2.6
sqlalchemy==2.0.0

# Utilities
python-dotenv==1.0.0
python-multipart==0.0.6
httpx==0.25.0
requests==2.31.0
```

### Adicionales por Servicio

**usuarios-service**: Base only

**eventos-service**: Base + redis

**reservas-service**: Base + redis + psycopg + sqlalchemy + httpx

---

## Build y Run

```bash
# Build individual
docker build -t eventflow-usuarios ./usuarios-service
docker build -t eventflow-eventos ./eventos-service
docker build -t eventflow-reservas ./reservas-service

# Run individual (requiere BDs corriendo)
docker run -d -p 8001:8001 --name usuarios \
  -e MONGODB_URI=mongodb://host.docker.internal:27017 \
  eventflow-usuarios
```

---

## Multi-stage Build (Producción)

```dockerfile
# Builder stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY src/ .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## Referencias

- [[deployment/docker-compose]] - docker-compose.yml completo
- [[deployment/deployment-checklist]] - Checklist pre-producción
- [[decisions/deployment-strategy]] - Estrategia completa