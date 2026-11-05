---
name: deployment-checklist
description: Checklist de verificación pre-producción para EventFlow
metadata:
  type: deployment
  status: complete
---

# Deployment Checklist - EventFlow

**Revisado 2026-11-05.** La sección *Pre-Deployment* refleja el estado real del proyecto (✅ verificado, ❌ no hecho). *Staging*, *Production* y *Post-Deployment* son una referencia de qué haría falta para producción: están fuera del alcance de la tarea y no se hicieron.

## Pre-Deployment (Desarrollo)

### Código y Tests
- [x] Todos los tests pasan: `make test` → usuarios 56, eventos 93, reservas 112 (+4 skipped)
- [x] Contract tests (OpenAPI; schemathesis en eventos)
- [x] Integration tests SAGA happy path + compensaciones + fault injection
- [x] Unit tests de los handlers de la Chain of Responsibility
- [ ] ❌ Coverage medido ≥ 80% (no se midió de forma sistemática)
- [ ] ❌ Sin secrets hardcodeados: las credenciales de desarrollo de PostgreSQL están en `docker-compose.yml`
- [ ] ❌ Linting (`flake8`/`black`/`mypy`) no configurado; reservas corre `pyflakes` en un test

### Docker
- [x] `make up` levanta todo healthy
- [x] Health checks pasan en los 7 contenedores
- [x] `docker compose ps` muestra 7 contenedores Up (healthy)
- [x] Logs estructurados (JSON) sin errores en el camino feliz
- [ ] ❌ Escaneo de vulnerabilidades de imágenes

### Funcionalidad Manual
- [x] POST /api/usuarios → 201, GET /api/usuarios/{id} → 200
- [x] GET /api/usuarios/exportar → JSON/CSV sin datos personales (verificado con grep sobre el export)
- [x] POST /api/eventos → 201, GET /api/eventos/{id} → 200 con aforo
- [x] POST /api/reservar (happy path) → 201; reintento mismo `reserva_id` → 200
- [x] POST /api/reservar (inventario insuficiente) → 409; (usuario inexistente) → 404
- [x] MongoDB: reserva + saga_log; historial del usuario actualizado
- [x] Redis: `pago:{reserva_id}` + inventario decrementado
- [x] PostgreSQL: 8 eventos ordenados en una compra exitosa (incluye `HISTORIAL_ACTUALIZADO`)
- [x] Compensación del paso 4 (`?simular_fallo=sync_pago`): aforo igual antes y después
- [x] Servicio caído (Eventos) → 503; al volver, reintento → 201 → 200
- [x] MongoDB caído → lecturas `STALE` desde la caché; lectura estricta → 503
- [x] `redis-cache` caído → lecturas desde MongoDB y compras 201; `redis` caído → lecturas `HIT` y compra 500 `PAYMENT_FAILED` (caídas independientes)
- [x] JMeter: doble venta 300 intentos / stock 50 → exactamente 50 ventas
- [ ] ❌ Compensación del paso 5 (fallo de MongoDB) probada solo en tests, no en vivo

---

## Pre-Production (Staging)

### Infraestructura
- [ ] MongoDB: Replica Set 3 nodos, readPreference secondaryPreferred configurado
- [ ] Redis: Cluster o Master-Replica + Sentinel, AOF enabled (hoy: `redis` con AOF y `redis-cache` sin persistencia, sin réplicas)
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
- [ ] Load test: 100 req/s concurrentes SAGA, p99 < 1s (**medido: no se cumple**, satura en ≈ 50 req/s; ver `jmeter/README.md`)
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
- [ ] Event log completo (8 eventos/reserva exitosa)
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

- [[docker-compose]] - docker-compose.yml
- [[docker-setup]] - Dockerfiles
- [[deployment-strategy]] - Estrategia (K8s solo diseño)
- [[saga-flow]] - Validación compensaciones
- [[chain-of-responsibility]] - Validación handlers