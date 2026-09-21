---
name: deployment-checklist
description: Checklist de verificación pre-producción para EventFlow
metadata:
  type: deployment
  status: complete
---

# Deployment Checklist - EventFlow

## Pre-Deployment (Desarrollo)

### Código y Tests
- [ ] Todos los tests pasan: `pytest -v` en cada servicio
- [ ] Contract tests pasan (OpenAPI compliance)
- [ ] Integration tests SAGA happy path + compensaciones
- [ ] Unit tests handlers Chain of Responsibility
- [ ] Coverage ≥ 80% en lógica de negocio
- [ ] No secrets hardcodeados (revisar `.env.example` vs `.env`)
- [ ] Linting pasa: `flake8`, `black --check`, `mypy`

### Docker
- [ ] `docker compose up -d --build` levanta todos los servicios healthy
- [ ] Health checks pasan en todos los contenedores
- [ ] `docker compose ps` muestra 6 contenedores Up (healthy)
- [ ] Logs sin errores críticos: `docker compose logs`
- [ ] Imágenes build sin vulnerabilidades críticas (`docker scan` o `trivy`)

### Funcionalidad Manual
- [ ] POST /api/usuarios → 201, GET /api/usuarios/{id} → 200
- [ ] GET /api/usuarios/exportar → JSON/CSV anonimizado sin PII
- [ ] POST /api/eventos → 201, GET /api/eventos/{id} → 200 con aforo
- [ ] POST /api/reservar (happy path) → 201 con confirmación
- [ ] POST /api/reservar (inventario insuficiente) → 409
- [ ] POST /api/reservar (usuario inexistente) → 404
- [ ] Verificar MongoDB: reserva + saga_log
- [ ] Verificar Redis: pago + inventario decrementado
- [ ] Verificar PostgreSQL: 7 eventos en event_log ordenados
- [ ] Probar compensación: fallo MongoDB → rollback Redis

---

## Pre-Production (Staging)

### Infraestructura
- [ ] MongoDB: Replica Set 3 nodos, readPreference secondaryPreferred configurado
- [ ] Redis: Cluster o Master-Replica + Sentinel, AOF enabled
- [ ] PostgreSQL: Primary-Standby con Patroni, backups automáticos
- [ ] Kubernetes: Deployments + Services + HPA configurados
- [ ] Ingress: TLS terminación, rate limiting, path routing
- [ ] Secrets: Vault/SealedSecrets para credenciales
- [ ] Network Policies: Calico/Cilium restrictivo

### Observabilidad
- [ ] Logging: JSON structured, correlation_id propagado
- [ ] Métricas: Prometheus + Grafana dashboards por servicio
- [ ] Tracing: Jaeger/Zipkin con correlation_id
- [ ] Alertas: Latencia p99 > 1s, error rate > 1%, SAGA failure rate > 0.1%
- [ ] Health checks: Kubernetes liveness/readiness probes

### Seguridad
- [ ] mTLS entre servicios (Istio/Linkerd)
- [ ] Autenticación/Autorización (OAuth2/OIDC)
- [ ] Rate limiting en Ingress
- [ ] Input validation en todos los endpoints
- [ ] No PII en logs (verificar anonimización)
- [ ] CORS configurado restrictivamente

### Performance
- [ ] Load test: 100 req/s concurrentes SAGA, p99 < 1s
- [ ] Stress test: 2x carga esperada, sin degradación
- [ ] Soak test: 1 hora carga sostenida, sin memory leaks
- [ ] Cache hit rate Redis > 90%
- [ ] MongoDB replica lag < 100ms
- [ ] PostgreSQL connection pooling configurado

---

## Production Go-Live

### Checklist Final
- [ ] Blue/Green o Rolling deployment configurado
- [ ] Rollback plan documentado y probado (< 5 min)
- [ ] Database migrations: zero-downtime (expand/contract pattern)
- [ ] Feature flags para nuevo funcionalidad
- [ ] Runbook de incidentes actualizado
- [ ] On-call rotation definida
- [ ] Post-deployment smoke tests automatizados
- [ ] Monitoreo 24/7 primer semana

### Documentación
- [ ] README.md actualizado con comandos de ejecución
- [ ] Diagramas de arquitectura (Mermaid en repo)
- [ ] API docs: Swagger UI accesible
- [ ] Runbooks por servicio
- [ ] Diagramas SAGA + Chain of Responsibility

---

## Post-Deployment (Día 1-7)

### Métricas Críticas
- [ ] SAGA success rate > 99.9%
- [ ] Compensación rate < 0.1%
- [ ] Latencia p95 < 500ms, p99 < 1s
- [ ] Error rate < 0.1%
- [ ] Cache hit rate > 90%
- [ ] MongoDB replica lag < 100ms
- [ ] PostgreSQL replication lag < 1s

### Validación Negocio
- [ ] Reservas creadas = pagos confirmados
- [ ] Inventario Redis = MongoDB entradas_disponibles
- [ ] Event log completo (7 eventos/reserva exitosa)
- [ ] Exportación GDPR funcional
- [ ] Número confirmación único y formato correcto

---

## Rollback Criteria

**Auto-rollback si**:
- SAGA success rate < 99% en 5 min
- Error rate > 5% en 2 min
- Latencia p99 > 5s sostenida 3 min
- Health checks failing > 3 servicios

**Manual rollback si**:
- Bug crítico en lógica de compensación
- Pérdida de datos detectada
- Vulnerabilidad seguridad crítica

---

## Referencias

- [[deployment/docker-compose]] - docker-compose.yml
- [[deployment/docker-setup]] - Dockerfiles
- [[decisions/deployment-strategy]] - Estrategia completa K8s
- [[architecture/saga-flow]] - Validación compensaciones
- [[architecture/chain-of-responsibility]] - Validación handlers