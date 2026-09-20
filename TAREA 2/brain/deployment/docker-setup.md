---
name: docker-setup
description: Configuración de Docker y Dockerfiles
metadata:
  type: specification
  status: draft
---

# Docker Setup

## Estructura de Directorios

```
eventflow/
├── docker-compose.yml
├── usuarios-service/
│   ├── Dockerfile
│   ├── src/
│   └── requirements.txt (Python) o package.json
├── eventos-service/
│   ├── Dockerfile
│   ├── src/
│   └── ...
├── reservas-service/
│   ├── Dockerfile
│   ├── src/
│   └── ...
└── .env (variables de entorno)
```

---

## Dockerfile Base (Python FastAPI)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## docker-compose.yml

Ver [[docker-compose-config]]

---

## Variables de Entorno (.env)

```
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=

SERVICE_USUARIOS_PORT=8001
SERVICE_EVENTOS_PORT=8002
SERVICE_RESERVAS_PORT=8003
```

---

## Comandos Útiles

```bash
# Construir imágenes
docker-compose build

# Iniciar servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar servicios
docker-compose down

# Ejecutar comando en container
docker-compose exec usuarios-service python -c "..."

# Recrear volumenes (reset BD)
docker-compose down -v && docker-compose up -d
```

---

## Health Checks

Agregar a cada servicio en docker-compose.yml:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

---

## Redes Docker

Los servicios se comunican por nombre de servicio:
```python
# En usuarios-service
response = requests.get("http://eventos-service:8002/api/eventos/123")
```

---

## Volúmenes Persistentes

```yaml
services:
  mongodb:
    volumes:
      - mongodb_data:/data/db
  redis:
    volumes:
      - redis_data:/data

volumes:
  mongodb_data:
  redis_data:
```

---

## Próximos Pasos

- [ ] Dockerfile optimizado para cada servicio
- [ ] docker-compose.yml funcional
- [ ] Health checks configurados
- [ ] Testeo de conexiones entre servicios
