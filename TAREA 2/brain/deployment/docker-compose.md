---
name: docker-compose
description: docker-compose.yml completo para desarrollo local
metadata:
  type: deployment
  status: complete
---

# Docker Compose - Desarrollo Local

## Archivo Completo

```yaml
# docker-compose.yml
# Ubicación: /home/fqueirolo/TECNOLOGO/NoSQL/TAREA 2/docker-compose.yml

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
      test: ["CMD", "mongosh", "--eval", "db.runCommand({ping: 1})"]
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
      ANONYMIZATION_SALT: eventflow-salt-2026-change-in-production
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
      REDIS_URL: redis://redis:6379
      SERVICE_PORT: 8002
    ports:
      - "8002:8002"
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
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

## Comandos de Ejecución

```bash
# Construir y levantar todo
docker compose up -d --build

# Ver estado
docker compose ps

# Ver logs
docker compose logs -f usuarios-service
docker compose logs -f reservas-service

# Ver logs de BDs
docker compose logs mongodb
docker compose logs redis
docker compose logs postgresql

# Detener
docker compose down

# Detener + limpiar volúmenes (CUIDADO: borra datos)
docker compose down -v

# Reconstruir un servicio
docker compose build usuarios-service
docker compose up -d usuarios-service

# Ejecutar tests dentro de contenedor
docker compose exec usuarios-service pytest -v
docker compose exec reservas-service pytest -v
```

---

## Puertos Expuestos (Host)

| Servicio | Puerto Contenedor | Puerto Host | Uso |
|----------|------------------|-------------|-----|
| MongoDB | 27017 | 27017 | Cliente MongoDB, debugging |
| Redis | 6379 | 6379 | Cliente Redis, debugging |
| PostgreSQL | 5432 | 5432 | pgAdmin, reportes |
| Usuarios | 8001 | 8001 | API + Swagger `/docs` |
| Eventos | 8002 | 8002 | API + Swagger `/docs` |
| Reservas | 8003 | 8003 | API + Swagger `/docs` |

---

## Variables de Entorno por Servicio

### Usuarios Service
```bash
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
SERVICE_PORT=8001
ANONYMIZATION_SALT=eventflow-salt-2026-change-in-production
```

### Eventos Service
```bash
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
REDIS_URL=redis://redis:6379
SERVICE_PORT=8002
```

### Reservas Service
```bash
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
REDIS_URL=redis://redis:6379
POSTGRESQL_URI=postgresql://eventflow_user:eventflow_password@postgresql:5432/eventflow
USUARIOS_SERVICE_URL=http://usuarios-service:8001
EVENTOS_SERVICE_URL=http://eventos-service:8002
SERVICE_PORT=8003
```

---

## Health Checks

| Servicio | Comando | Intervalo | Timeout | Reintentos |
|----------|---------|-----------|---------|------------|
| MongoDB | `mongosh --eval "db.runCommand({ping:1})"` | 10s | 5s | 3 |
| Redis | `redis-cli ping` | 10s | 5s | 3 |
| PostgreSQL | `pg_isready -U eventflow_user` | 10s | 5s | 3 |
| Usuarios | `curl -f http://localhost:8001/health` | 10s | 5s | 3 |
| Eventos | `curl -f http://localhost:8002/health` | 10s | 5s | 3 |
| Reservas | `curl -f http://localhost:8003/health` | 10s | 5s | 3 |

---

## Red y Volúmenes

```yaml
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

## Troubleshooting

| Problema | Solución |
|----------|----------|
| MongoDB unhealthy | Verificar `mongosh --eval "db.runCommand({ping:1})"` funciona |
| Servicios no inician | `docker compose logs <servicio>` - revisar dependencias |
| Puerto ocupado | Cambiar puerto host en `ports:` o detener proceso local |
| Permisos volúmenes | `docker compose down -v` y reconstruir |
| Redis connection refused | Verificar `redis-cli ping` en contenedor redis |

---

## Referencias

- [[deployment/docker-setup]] - Dockerfiles por servicio
- [[deployment/deployment-checklist]] - Checklist pre-producción
- [[decisions/deployment-strategy]] - Estrategia completa