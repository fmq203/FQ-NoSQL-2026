---
name: learnings
description: Notas de aprendizajes, decisiones fallidas e insights técnicos
metadata:
  type: learnings
  status: in-progress
---

# Learnings & Notas

## 2026-09-20

### Decisión: PostgreSQL como Event Log (Append-Only)

**Contexto:** Después de planificar MongoDB + Redis, se agregó PostgreSQL.

**Por qué:** 
- MongoDB + Redis resuelve performance y atomicidad
- Pero no hay forma limpia de auditoría legal/compliance
- PostgreSQL con Event Log (append-only) es patrón probado en industria

**Insight:**
- 3 BDs es mejor que 2 cuando:
  - Tienes datos de negocio (MongoDB)
  - Necesitas transacciones atómicas (Redis)
  - Necesitas auditoría legal (PostgreSQL)
- PostgreSQL NO compite con MongoDB/Redis — es complementario
- Event Log es el "black box recorder" del sistema (quién, qué, cuándo)

**Decisión:** MongoDB + Redis + PostgreSQL (3-Database Architecture)

**Implicación:** Mayor complejidad operacional pero auditoría garantizada (GDPR compliant)

---

### Decisión: MongoDB + Redis vs MongoDB Solo

**Contexto:** Discusión sobre qué BDs usar.

**Consideración:** ¿Una sola BD es más simple?

**Insight:**
- MongoDB solo sería más simple operacionalmente
- Pero sacrificaría consistencia en pagos (critical path)
- Redis Lua scripts garantizan atomicidad que MongoDB no puede hacer en read-heavy scenarios
- **Conclusión:** MongoDB + Redis es la decisión correcta, complejidad justificada

**Implicación:** Preparar equipo para debug distribuido + consistencia eventual

---

### Decisión: SAGA Orchestration vs Event Sourcing

**Opción 1:** SAGA Orchestration (Reservas Service orquesta)
- Pros: Simpler, clearer control flow
- Cons: Orquestador es punto único de fallo

**Opción 2:** Event Sourcing (cada servicio emite eventos)
- Pros: Más resiliente, auditoria natural
- Cons: Más complejo, requiere message broker (RabbitMQ, Kafka)

**Decisión:** SAGA Orchestration (Opción 1) para MVP

**Razón:** Tiempo de entrega 5 nov pre-defensa, complejidad. Event Sourcing es sección opcional.

**Futuro:** Si tenemos tiempo, explorar Event Sourcing + CQRS como enhancement

---

### Chain of Responsibility: Ventajas de Validadores Modulares

**Insight:** Al separar validadores (datos → inventario → pago):
- Testing mucho más fácil (mock de cada validador)
- Reuso en otros flows (ej: cancelación de reserva)
- Logging granular en cada punto de validación

**Aprendizaje:** No ahorrar tiempo saltando la modularidad — se paga el precio después

---

## 2026-09-20 (Futura)

_Espacio para más learnings a medida que avanza el proyecto_

---

## Decisiones Fallidas (Historias de Desastres Evitados)

### ❌ Idea: Usar Solo Redis para Inventario

**Por qué se consideró:** Redis es super rápido.

**Por qué falló:** Redis in-memory, si cae el servicio sin persistence, pierdes el estado de inventario.

**Lección:** Usar Redis para transacciones (stateless), MongoDB para estado persistente.

---

### ❌ Idea: No implementar timeouts en SAGA

**Por qué se consideró:** Simplificar lógica.

**Por qué habría fallado:** Si Eventos Service se cuelga, SAGA queda en limbo indefinidamente.

**Lección:** Siempre agregar timeouts (5s) + circuit breaker en llamadas distribuidas.

---

## Preguntas Abiertas

- ¿Cómo manejamos la idempotencia en reintents del cliente?
  - Respuesta temporal: Guardar `request_id` en Redis, devolver resultado si existe
  
- ¿Qué pasa si MongoDB está down durante SAGA Step 5?
  - Respuesta: SAGA rollback, cliente reintenta (idempotente)

- ¿Escalabilidad de Redis si tenemos millones de transacciones/día?
  - Respuesta: Redis Cluster mode (sharding por usuario_id/evento_id)

---

## Insights Técnicos

### Lua Scripts en Redis

**Ventaja:** Atomicidad garantizada (sin race conditions)

**Aprendizaje:** Escribir scripts Lua es diferente a Python/JS. Necesita testing cuidadoso.

### Eventual Consistency para Lecturas

**Ventaja:** MongoDB read-only queries pueden ir a replicas (fast)

**Ventaja:** Caché con Redis TTL (5 min) para eventos calientes

**Cuidado:** Usuario ver info stale de inventario, pero compra falla si stock actual es bajo (SAGA Step 2 lo detecta). Experiencia: "Ya no hay entradas" — Aceptable.

---

## Métricas a Trackear

- Latencia P95 de POST /reservar
- Tasa de SAGA failures (compensations)
- Hit ratio de caché Redis
- Replication lag MongoDB

---

## Próximos Pasos de Investigación

- [ ] ¿Cómo implementar circuit breaker en Python FastAPI?
- [ ] ¿Redis Sentinel vs Cluster para HA?
- [ ] ¿Cómo testear compensaciones sin afectar BD real?
- [ ] ¿Tooling de observabilidad (Prometheus + Grafana)?
