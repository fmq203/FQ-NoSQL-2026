---
name: requirements
description: Dependencias y requisitos de desarrollo para EventFlow
metadata:
  type: specification
  status: draft
---

# Requisitos & Dependencias

## 🐍 Python (FastAPI)

### Base
```bash
# requirements.txt
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.0.0
pydantic-extra-types==2.0.0
```

### Base de Datos
```bash
pymongo==4.5.0          # MongoDB driver
redis==5.0.0            # Redis driver
psycopg[binary]==3.17   # PostgreSQL driver
sqlalchemy==2.0.0       # ORM (opcional, para PostgreSQL)
```

### Utilidades
```bash
python-dotenv==1.0.0    # Variables de entorno
python-multipart==0.0.6 # Multipart form data
httpx==0.25.0           # HTTP client (para llamadas entre servicios)
```

### Spec-kit & Documentación
```bash
spec-kit==1.0.0         # GitHub spec-kit (OpenAPI)
swagger-ui-py==4.0.0    # Swagger UI en /docs
```

### Testing (Opcional)
```bash
pytest==7.4.0
pytest-asyncio==0.21.0
pytest-cov==4.1.0
httpx==0.25.0           # Test client
factory-boy==3.3.0      # Test fixtures
faker==19.0.0           # Fake data
```

---

## 🐳 Docker & Compose

### Versiones Requeridas
- Docker: >= 20.10
- Docker Compose: >= 2.0
- Python: 3.11+

### Instalación (Ubuntu/Debian)
```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

---

## 📦 Especificación de Servicios

### Usuarios Service
```dockerfile
FROM python:3.11-slim
RUN pip install -r requirements.txt && \
    npm install -g @github/spec-kit
COPY . /app
WORKDIR /app
RUN spec-kit generate --output spec.json
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🗄️ Bases de Datos

### MongoDB
- **Docker:** `mongo:7.0`
- **Driver:** `pymongo==4.5.0`
- **URI:** `mongodb://mongodb:27017`

### Redis
- **Docker:** `redis:7.0-alpine`
- **Driver:** `redis==5.0.0`
- **URI:** `redis://redis:6379`

### PostgreSQL
- **Docker:** `postgres:15-alpine`
- **Driver:** `psycopg[binary]==3.17`
- **URI:** `postgresql://user:pass@postgresql:5432/eventflow`

---

## 🔧 Herramientas de Desarrollo

### Local Development
```bash
pip install -r requirements-dev.txt

# Incluye:
# - black (code formatter)
# - flake8 (linter)
# - mypy (type checker)
# - pytest (testing)
# - spec-kit (OpenAPI)
```

### Pre-commit Hooks
```bash
pip install pre-commit

# Crear .pre-commit-config.yaml:
repos:
  - repo: https://github.com/psf/black
    rev: 23.0.0
    hooks:
      - id: black

  - repo: https://github.com/charliermarsh/ruff
    rev: 0.0.292
    hooks:
      - id: ruff

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: 1.0.0
    hooks:
      - id: mypy

  - repo: https://github.com/github/spec-kit
    rev: 1.0.0
    hooks:
      - id: spec-kit-validate
```

### IDE Recomendado
- **VS Code** + extensions:
  - Python (Microsoft)
  - Pylance
  - REST Client
  - Thunder Client (o Postman)
  - MongoDB for VS Code
  - PostgreSQL (Chris Kolkman)

---

## 📋 Checklist Pre-Desarrollo

- [ ] Python 3.11+ instalado
- [ ] Docker & Docker Compose instalados
- [ ] MongoDB, Redis, PostgreSQL en `docker-compose.yml`
- [ ] `spec-kit` instalado globalmente
- [ ] `requirements.txt` con todas las dependencias
- [ ] `.env` configurado (MONGODB_URI, REDIS_URL, etc.)
- [ ] Pre-commit hooks configurados
- [ ] IDE configurado con linters

---

## 🚀 Inicio Rápido

```bash
# 1. Clonar repo
git clone <repo>
cd eventflow

# 2. Crear virtual env
python3.11 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Iniciar BDs (Docker)
docker-compose up -d

# 5. Iniciar Usuarios Service
cd usuarios-service
spec-kit generate --output spec.json
uvicorn src.main:app --reload

# 6. Ver Swagger UI
open http://localhost:8001/docs
```

---

## 📝 requirements-dev.txt

```txt
# Incluir todo de requirements.txt
-r requirements.txt

# Desarrollo
black==23.0.0
flake8==6.0.0
mypy==1.0.0
pylint==2.16.0

# Testing
pytest==7.4.0
pytest-asyncio==0.21.0
pytest-cov==4.1.0
factory-boy==3.3.0
faker==19.0.0

# Pre-commit
pre-commit==3.3.0

# API Testing
httpx==0.25.0
requests==2.31.0

# Documentación (Opcional)
sphinx==7.0.0
sphinx-rtd-theme==1.2.0
```

---

## 🔐 Variables de Entorno (.env)

```bash
# .env (NO commitear a Git)

# MongoDB
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow

# Redis
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=

# PostgreSQL
POSTGRESQL_URI=postgresql://eventflow_user:eventflow_password@postgresql:5432/eventflow

# Services
USUARIOS_SERVICE_URL=http://usuarios-service:8001
EVENTOS_SERVICE_URL=http://eventos-service:8002
RESERVAS_SERVICE_URL=http://reservas-service:8003

# App
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## 📦 Versiones Probadas

| Herramienta | Versión | Fecha |
|------------|---------|-------|
| Python | 3.11 | 2026-09-20 |
| FastAPI | 0.104.0 | 2026-09-20 |
| MongoDB | 7.0 | 2026-09-20 |
| Redis | 7.0 | 2026-09-20 |
| PostgreSQL | 15 | 2026-09-20 |
| spec-kit | 1.0.0 | 2026-09-20 |
| Docker | 24.0 | 2026-09-20 |

---

## ⚠️ Problemas Comunes

### spec-kit no genera spec.json
```bash
# Solución
spec-kit generate --output spec.json --verbose
```

### Puerto 8001 ya en uso
```bash
# Cambiar puerto
uvicorn main:app --port 8002
```

### MongoDB connection refused
```bash
# Asegurar que docker-compose está corriendo
docker-compose up -d
docker-compose logs mongodb
```

---

## 🔗 Referencias

- [[spec-kit-setup]] — Configuración spec-kit
- [[docker-compose-config]] — docker-compose.yml
- [[spec-kit-code-example.py]] — Ejemplo con decoradores
