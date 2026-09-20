---
name: docker-compose-config
description: Plantilla de docker-compose.yml
metadata:
  type: specification
  status: draft
---

# docker-compose.yml Template

```yaml
version: '3.9'

services:
  # ============ MONGODB ============
  mongodb:
    image: mongo:7.0
    container_name: eventflow_mongodb
    environment:
      MONGO_INITDB_DATABASE: eventflow
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.admin.ping()"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - eventflow_network

  # ============ REDIS ============
  redis:
    image: redis:7.0-alpine
    container_name: eventflow_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - eventflow_network

  # ============ POSTGRESQL ============
  postgresql:
    image: postgres:15-alpine
    container_name: eventflow_postgresql
    environment:
      POSTGRES_DB: eventflow
      POSTGRES_USER: eventflow_user
      POSTGRES_PASSWORD: eventflow_password
    ports:
      - "5432:5432"
    volumes:
      - postgresql_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U eventflow_user"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - eventflow_network

  # ============ USUARIOS SERVICE ============
  usuarios-service:
    build:
      context: ./usuarios-service
      dockerfile: Dockerfile
    container_name: eventflow_usuarios
    environment:
      MONGODB_URI: mongodb://mongodb:27017
      MONGODB_DB: eventflow
      SERVICE_PORT: 8001
    ports:
      - "8001:8001"
    depends_on:
      mongodb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - eventflow_network

  # ============ EVENTOS SERVICE ============
  eventos-service:
    build:
      context: ./eventos-service
      dockerfile: Dockerfile
    container_name: eventflow_eventos
    environment:
      MONGODB_URI: mongodb://mongodb:27017
      MONGODB_DB: eventflow
      SERVICE_PORT: 8002
    ports:
      - "8002:8002"
    depends_on:
      mongodb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - eventflow_network

  # ============ RESERVAS SERVICE (ORQUESTADOR) ============
  reservas-service:
    build:
      context: ./reservas-service
      dockerfile: Dockerfile
    container_name: eventflow_reservas
    environment:
      MONGODB_URI: mongodb://mongodb:27017
      MONGODB_DB: eventflow
      REDIS_URL: redis://redis:6379
      POSTGRESQL_URI: postgresql://eventflow_user:eventflow_password@postgresql:5432/eventflow
      USUARIOS_SERVICE_URL: http://usuarios-service:8001
      EVENTOS_SERVICE_URL: http://eventos-service:8002
      SERVICE_PORT: 8003
    ports:
      - "8003:8003"
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
      postgresql:
        condition: service_healthy
      usuarios-service:
        condition: service_healthy
      eventos-service:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - eventflow_network

networks:
  eventflow_network:
    driver: bridge

volumes:
  mongodb_data:
    driver: local
  redis_data:
    driver: local
  postgresql_data:
    driver: local
```

---

## Notas

- **Orden de inicio:** Docker Compose espera a `depends_on` + `healthcheck`
- **Redes:** Los servicios se comunican por nombre (eg. `http://usuarios-service:8001`)
- **Volúmenes:** `mongodb_data` y `redis_data` persisten datos entre reinicios
- **Puertos:** Mapeados para pruebas locales

---

## Comandos

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f reservas-service

# Test usuarios service
curl http://localhost:8001/health

# Restart specific service
docker-compose restart reservas-service

# Remove everything
docker-compose down -v
```
