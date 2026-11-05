# 🧠 EventFlow Brain — Second Brain para Tarea 2 NoSQL

Bienvenido al **segundo cerebro del proyecto EventFlow**. Este es un repositorio de conocimiento estructurado en Markdown que organiza toda la arquitectura, decisiones y patrones de diseño.

---

## 🚀 Uso Rápido

**Punto de entrada:** Comienza en [`CLAUDE.md`](./CLAUDE.md) (el mapa) o [`index.md`](./index.md) (el catálogo).

**Para el equipo:** Lee primero [`decisions/db-selection.md`](./decisions/db-selection.md) para entender por qué MongoDB + Redis.

**Para los desarrolladores:** Ve directamente a [`microservices/`](./microservices/) para especificaciones de cada servicio.

---

## 📂 Estructura

```
brain/
├── CLAUDE.md              ← mapa (leer primero)
├── index.md               ← catálogo completo con enlaces
├── decisions/             db-selection, three-database-strategy, consistency-strategy, deployment-strategy
├── architecture/          overview, microservices-diagram, data-flow, saga-flow
├── microservices/         usuarios, eventos, reservas-pagos
├── endpoints/             usuarios-, eventos-, reservas-endpoints
├── data-models/           user-, event-, reservation-, event-log-schema, db-choice-rationale
├── patterns/              saga-pattern, chain-of-responsibility, event-log-pattern, event-sourcing-cqrs
├── deployment/            docker-setup, docker-compose, deployment-checklist, requirements,
│                          spec-kit-setup, postgresql-init.sql (+ 2 bocetos históricos)
└── learnings/learnings.md ← registro append-only (incluye interacciones con IA)
```

Todo el brain fue revisado contra el código el **2026-11-05**: lo que dice cada doc es lo que hace el código, y lo que no está implementado está marcado como tal.

---

## 📊 Estado del Proyecto

| Componente | Estado | Link |
|-----------|--------|------|
| **Decisiones de BD (3x)** | ✅ Done | [`db-selection.md`](./decisions/db-selection.md) |
| **Estrategia 3 BDs** | ✅ Done | [`three-database-strategy.md`](./decisions/three-database-strategy.md) |
| **Estrategia Consistencia** | ✅ Done | [`consistency-strategy.md`](./decisions/consistency-strategy.md) |
| **Arquitectura Overview** | ✅ Done | [`overview.md`](./architecture/overview.md) |
| **Microservicios Spec** | ✅ Done | [`microservices/`](./microservices/) |
| **Endpoints APIs** | ✅ Done | [`endpoints/`](./endpoints/) (OpenAPI generada por FastAPI) |
| **Spec Kit (spec-driven)** | ✅ Done | [`spec-kit-setup.md`](./deployment/spec-kit-setup.md), `.specify/specs/` |
| **Data Models** | ✅ Done | [`data-models/`](./data-models/) |
| **Event Log Schema** | ✅ Done | [`event-log-schema.md`](./data-models/event-log-schema.md) |
| **SAGA Pattern** | ✅ Done | [`saga-pattern.md`](./patterns/saga-pattern.md) |
| **Event Log Pattern** | ✅ Done | [`event-log-pattern.md`](./patterns/event-log-pattern.md) |
| **Chain of Responsibility** | ✅ Done | [`chain-of-responsibility.md`](./patterns/chain-of-responsibility.md) |
| **Docker Setup** | ✅ Done | [`docker-setup.md`](./deployment/docker-setup.md) |
| **docker-compose.yml** | ✅ Done | [`docker-compose.md`](./deployment/docker-compose.md) |
| **Event Sourcing/CQRS** | ✅ Done | Vistas `ventas_por_evento`/`tasa_exito_saga`/`compensaciones_por_tipo` + índice GIN en `reservas-service/src/services/postgresql.py::init_pg_schema()` |
| **Implementación Código** | ✅ Done | usuarios-service, eventos-service, reservas-service (SAGA + Chain of Responsibility) implementados y corriendo vía `docker compose` |
| **Tests** | ✅ Done | `make test`: usuarios 56, eventos 93, reservas 112 (+4 skipped) |
| **Caché AP de lecturas** | ✅ Done | [`consistency-strategy.md`](./decisions/consistency-strategy.md) |
| **Export anonimizado** | ✅ Done | [`user-schema.md`](./data-models/user-schema.md) |
| **JMeter** | ✅ Done | `jmeter/README.md`: sin doble venta; la compra satura en ≈ 50 req/s |
| **Demo** | ✅ Done | `demo/` (`python3 demo/servidor.py`) |

---

## 🎯 Para los Desarrolladores

### Paso 1: Entiende la Arquitectura
```
1. Lee CLAUDE.md (2 min)
2. Lee architecture/overview.md (5 min)
3. Lee decisions/db-selection.md (3 min)
```

### Paso 2: Toma tu Microservicio
```
- Usuarios → Lee microservices/usuarios.md + endpoints/usuarios-endpoints.md
- Eventos → Lee microservices/eventos.md + endpoints/eventos-endpoints.md
- Reservas → Lee microservices/reservas-pagos.md + patterns/saga-pattern.md
```

### Paso 3: Implementa Usando el Schema
```
- Revisa data-models/{tu-schema}.md para estructura de datos
- Sigue endpoints/{tu-service}-endpoints.md para API
- Implementa validaciones en patterns/chain-of-responsibility.md
```

### Paso 4: Testea Localmente
```
make up      # build + levanta todo
make test    # suites de los 3 servicios en sus contenedores
# Dentro de la red de compose: mongodb://mongodb:27017, redis://redis:6379,
# postgresql://...@postgresql:5432/eventflow, http://<servicio>-service:<puerto>
```

---

## 💡 Notas Importantes

### SAGA Orchestration
- El Servicio de Reservas es el **orquestador central**
- Coordina transacción con compensaciones en caso de fallo
- Ver: [`patterns/saga-pattern.md`](./patterns/saga-pattern.md)

### Consistencia
- **Lecturas (Usuarios, Eventos):** Eventual (caché Redis stale-if-error; MongoDB en un solo nodo)
- **Escrituras (Reservas, Pagos):** Fuerte (Lua atómico + idempotencia + SAGA con compensación)
- Ver: [`decisions/consistency-strategy.md`](./decisions/consistency-strategy.md)

### Data Modeling
- **MongoDB:** Embedded arrays para historial (no referencias)
- **Redis:** Lua scripts para atomicidad de pagos
- Ver: [`data-models/`](./data-models/)

---

## 🔗 Convenciones del Brain

- **Links internos:** `[[nombre-archivo]]` (facilita navegación)
- **Status:** `draft | in-progress | complete`
- **Actualizaciones:** Modificar archivo + actualizar `last-updated`
- **Nuevos archivos:** Agregar a `index.md` automáticamente

---

## 📅 Fechas Clave

- **Pre-defensa:** Jueves 5 de noviembre de 2026
- **Defensa final:** Jueves 12 de noviembre de 2026
- **Tiempo presentación:** ~12 min (demo + arquitectura)

---

## 🤝 Cómo Mantener el Brain

1. **Después de cada sesión:** Actualiza `learnings.md` con insights
2. **Antes de coded:** Verifica documentación en el brain (no inventes)
3. **Al descubrir problema:** Registra en `learnings.md` + solución
4. **Al terminar feature:** Marca status como `complete`

---

## 🆘 Preguntas Frecuentes

**P: ¿Por qué MongoDB + Redis?**  
R: Ver [`decisions/db-selection.md`](./decisions/db-selection.md) — MongoDB para datos eventuales, Redis para transacciones atómicas de pagos.

**P: ¿Cómo funciona SAGA?**  
R: Ver [`patterns/saga-pattern.md`](./patterns/saga-pattern.md) — pasos secuenciales + compensaciones automáticas en caso de fallo.

**P: ¿Qué es Chain of Responsibility?**  
R: Ver [`patterns/chain-of-responsibility.md`](./patterns/chain-of-responsibility.md) — cadena modular de validadores.

**P: ¿Cómo inicio los servicios?**  
R: `make up` desde `TAREA 2/`. Ver [`deployment/docker-compose.md`](./deployment/docker-compose.md).

---

## 🤖 Registro de Interacciones con IA

Para mantener trazabilidad y reproducibilidad, todas las interacciones significativas con IA se registran en el brain:

### Qué Registrar
| Tipo | Qué Incluir | Dónde |
|------|-------------|-------|
| **Decisiones de diseño** | Problema → Opciones → Decisión → Justificación | `decisions/` |
| **Arquitectura** | Diagramas, flujos, justificaciones | `architecture/` |
| **Implementación** | Patrones usados, código clave, trade-offs | `patterns/`, `microservices/` |
| **Problemas/Bloqueos** | Error, diagnóstico, solución, prevención | `learnings.md` |
| **Decisiones revertidas** | Qué se intentó, por qué falló, alternativa | `learnings.md` |

### Cómo Registrar
```markdown
## YYYY-MM-DD — Título breve
**Contexto:** Qué se estaba haciendo
**Problema/Decisión:** Qué surgió
**Análisis:** Opciones consideradas
**Decisión/Resultado:** Qué se eligió y por qué
**Próximos pasos:** Acciones pendientes
```

### Dónde Registrar
| Contenido | Archivo |
|-----------|---------|
| Decisiones arquitectónicas | `decisions/*.md` |
| Problemas/soluciones | `learnings.md` (append) |
| Cambios en código | Commit message + PR description |
| Insights técnicos | `learnings.md` (append) |
| Actualizaciones docs | Commit message + archivo modificado |

### Formato de Entrada en `learnings.md`
```markdown
### YYYY-MM-DD — Título descriptivo
**Contexto:** ...
**Problema:** ...
**Análisis:** ...
**Decisión:** ...
**Resultado:** ...
**Tags:** #tag1 #tag2
```

---

## 📝 Última Actualización

**2026-11-05** — Revisión completa del brain contra el código: endpoints, modelos, índices, claves Redis, Lua, payloads del event_log, read preferences reales, Dockerfiles y variables de entorno. Se reescribieron los docs que describían el diseño inicial en vez de lo implementado y se marcaron como históricos los bocetos que no corresponden. Detalle y hallazgos en [`learnings/learnings.md`](./learnings/learnings.md).
