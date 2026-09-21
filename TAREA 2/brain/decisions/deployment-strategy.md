---
name: deployment-strategy
description: Estrategia de despliegue para EventFlow
metadata:
  type: decision
  status: complete
---

# Decisión: Estrategia de Despliegue

## Problema

Desplegar 3 microservicios + 3 bases de datos con:
- Desarrollo local sencillo
- Health checks automáticos
- Escalabilidad futura
- Observabilidad básica

---

## Decisión: Docker Compose para Desarrollo, Kubernetes-ready para Producción

### Desarrollo Local: Docker Compose

```yaml
# docker-compose.yml - Ya implementado
services:
  mongodb:    # MongoDB 7.0
  redis:      # Redis 7.0-alpine
  postgresql: # PostgreSQL 15-alpine
  usuarios-service:  # Python FastAPI
  eventos-service:   # Python FastAPI
  reservas-service:  # Python FastAPI
```

**Características:**
- `depends_on` con `condition: service_healthy`
- Health checks en todos los servicios (`curl /health`)
- Red bridge compartida `eventflow_network`
- Volúmenes nombrados para persistencia
- Variables de entorno por servicio

### Producción: Kubernetes (Preparado)

| Componente | K8s Resource | Configuración |
|------------|--------------|---------------|
| Microservicios | Deployment + Service + HPA | 3+ replicas, CPU/memory limits |
| MongoDB | StatefulSet / Operator | ReplicaSet 3 nodos, persistent volumes |
| Redis | StatefulSet / Operator | Master-replica + Sentinel |
| PostgreSQL | StatefulSet / Operator | Primary-standby + Patroni |
| Ingress | IngressController | TLS, rate limiting, path routing |
| Config | ConfigMap + Secrets | Variables de entorno, credenciales |

---

## Health Checks Implementados

| Servicio | Comando | Intervalo | Timeout | Reintentos |
|----------|---------|-----------|---------|------------|
| MongoDB | `mongosh --eval "db.runCommand({ping:1})"` | 10s | 5s | 3 |
| Redis | `redis-cli ping` | 10s | 5s | 3 |
| PostgreSQL | `pg_isready -U eventflow_user` | 10s | 5s | 3 |
| Usuarios | `curl -f http://localhost:8001/health` | 10s | 5s | 3 |
| Eventos | `curl -f http://localhost:8002/health` | 10s | 5s | 3 |
| Reservas | `curl -f http://localhost:8003/health` | 10s | 5s | 3 |

---

## Variables de Entorno

### Por Servicio

```bash
# Usuarios Service
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
SERVICE_PORT=8001

# Eventos Service
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
SERVICE_PORT=8002

# Reservas Service
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=eventflow
REDIS_URL=redis://redis:6379
POSTGRESQL_URI=postgresql://eventflow_user:eventflow_password@postgresql:5432/eventflow
USUARIOS_SERVICE_URL=http://usuarios-service:8001
EVENTOS_SERVICE_URL=http://eventos-service:8002
SERVICE_PORT=8003
```

### Bases de Datos

```bash
# MongoDB
MONGO_INITDB_DATABASE=eventflow

# Redis
# Sin auth en desarrollo (--requirepass en prod)

# PostgreSQL
POSTGRES_DB=eventflow
POSTGRES_USER=eventflow_user
POSTGRES_PASSWORD=eventflow_password
```

---

## Puertos Expuestos (Host)

| Servicio | Puerto Contenedor | Puerto Host | Uso |
|----------|------------------|-------------|-----|
| MongoDB | 27017 | 27017 | Cliente MongoDB, debugging |
| Redis | 6379 | 6379 | Cliente Redis, debugging |
| PostgreSQL | 5432 | 5432 | pgAdmin, reportes, debugging |
| Usuarios | 8001 | 8001 | API Usuarios, Swagger `/docs` |
| Eventos | 8002 | 8002 | API Eventos, Swagger `/docs` |
| Reservas | 8003 | 8003 | API Reservas, Swagger `/docs` |

---

## Comandos de Ejecución

```bash
# Construir y levantar todo
docker compose up -d --build

# Ver logs
docker compose logs -f usuarios-service
docker compose logs -f reservas-service

# Ver estado
docker compose ps

# Detener
docker compose down

# Detener + volúmenes (LIMPIEZA TOTAL)
docker compose down -v

# Reconstruir un servicio
docker compose build usuarios-service
docker compose up -d usuarios-service

# Ejecutar tests
docker compose exec usuarios-service pytest
docker compose exec reservas-service pytest
```

---

## Escalabilidad Futura (Kubernetes)

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: reservas-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: reservas-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### MongoDB Sharding (Futuro)

```javascript
// Shard key por usuario_id para distribuir reservas
sh.shardCollection("eventflow.reservas", { "usuario_id": "hashed" })

// Shard key por evento_id para consultas de evento
sh.shardCollection("eventflow.eventos", { "fecha": 1, "_id": "hashed" })
```

---

## Seguridad (Producción)

- [ ] TLS/mTLS entre servicios (Istio/Linkerd)
- [ ] Secrets management (Vault/SealedSecrets)
- [ ] Network policies (Calico/Cilium)
- [ ] Rate limiting en Ingress
- [ ] Authentication/Authorization (OAuth2/OIDC)
- [ ] Audit logging centralizado (ELK/Loki)

---

## Referencias

- [[deployment/docker-compose]] — Archivo docker-compose.yml completo
- [[deployment/docker-setup]] — Dockerfiles por servicio
- [[deployment/deployment-checklist]] — Checklist pre-producción