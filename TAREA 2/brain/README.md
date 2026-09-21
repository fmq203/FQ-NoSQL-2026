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
├── CLAUDE.md                          ← MAPA PRINCIPAL (Lee primero!)
├── index.md                           ← Catálogo master
│
├── decisions/                         ← Decisiones arquitectónicas
│   ├── db-selection.md               ✅ MongoDB + Redis justificado
│   └── consistency-strategy.md        ✅ AP vs CP por operación
│
├── architecture/                      ← Diagramas y overview
│   ├── overview.md                   ✅ Vista general del sistema
│   └── (diagrama-images-TBD)
│
├── microservices/                     ← Especificación de cada service
│   ├── usuarios.md                   ✅ GET/POST usuarios
│   ├── eventos.md                    ✅ GET/POST eventos
│   └── reservas-pagos.md             ✅ SAGA orchestrator
│
├── endpoints/                         ← APIs REST
│   ├── usuarios-endpoints.md         ✅ POST/GET usuarios
│   ├── eventos-endpoints.md          ✅ POST/GET eventos
│   └── reservas-endpoints.md         ✅ POST /reservar (SAGA)
│
├── data-models/                       ← Schemas NoSQL
│   ├── user-schema.md                ✅ MongoDB usuario
│   ├── event-schema.md               ✅ MongoDB evento
│   └── reservation-schema.md         ✅ Redis reserva (atomic)
│
├── patterns/                          ← Patrones de diseño
│   ├── saga-pattern.md               ✅ SAGA orchestration
│   ├── chain-of-responsibility-pattern.md ✅ Validadores modulares
│   └── event-sourcing-cqrs.md        ⏳ (Opcional)
│
├── deployment/                        ← Docker & deploy
│   ├── docker-setup.md               ✅ Dockerfiles
│   ├── docker-compose.md             ✅ Compose template
│   └── deployment-checklist.md       ⏳ (TBD)
│
└── learnings/                         ← Apuntes y insights
    └── learnings.md                  ✅ Aprendizajes en vivo
```

---

## 📊 Estado del Proyecto

| Componente | Estado | Link |
|-----------|--------|------|
| **Decisiones de BD (3x)** | ✅ Done | [`db-selection.md`](./decisions/db-selection.md) |
| **Estrategia 3 BDs** | ✅ Done | [`three-database-strategy.md`](./decisions/three-database-strategy.md) |
| **Estrategia Consistencia** | ✅ Done | [`consistency-strategy.md`](./decisions/consistency-strategy.md) |
| **Arquitectura Overview** | ✅ Done | [`overview.md`](./architecture/overview.md) |
| **Microservicios Spec** | ✅ Done | [`microservices/`](./microservices/) |
| **Endpoints APIs (spec-kit)** | ✅ Done | [`spec-kit-setup.md`](./deployment/spec-kit-setup.md) |
| **OpenAPI Template** | ✅ Done | [`openapi-template.json`](./deployment/openapi-template.json) |
| **Code Example** | ✅ Done | [`spec-kit-code-example.py`](./deployment/spec-kit-code-example.py) |
| **Data Models** | ✅ Done | [`data-models/`](./data-models/) |
| **Event Log Schema** | ✅ Done | [`event-log-schema.md`](./data-models/event-log-schema.md) |
| **SAGA Pattern** | ✅ Done | [`saga-pattern.md`](./patterns/saga-pattern.md) |
| **Event Log Pattern** | ✅ Done | [`event-log-pattern.md`](./patterns/event-log-pattern.md) |
| **Chain of Responsibility** | ✅ Done | [`chain-of-responsibility-pattern.md`](./patterns/chain-of-responsibility-pattern.md) |
| **Docker Setup** | ✅ Done | [`docker-setup.md`](./deployment/docker-setup.md) |
| **docker-compose.yml** | ✅ Done | [`docker-compose.md`](./deployment/docker-compose.md) |
| **Event Sourcing/CQRS** | ⏳ Opcional | (Investigar después de MVP) |
| **Implementación Código** | 🔲 Next | (Developers: usar este brain como referencia) |
| **Tests** | 🔲 Next | (Unit + integration) |

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
- Implementa validaciones en patterns/chain-of-responsibility-pattern.md
```

### Paso 4: Testea Localmente
```
docker-compose up -d
# Tu service ahora se conecta a:
# - MongoDB: mongodb://mongodb:27017
# - Redis: redis://redis:6379
# - Otros services: http://service-name:port
```

---

## 💡 Notas Importantes

### SAGA Orchestration
- El Servicio de Reservas es el **orquestador central**
- Coordina transacción con compensaciones en caso de fallo
- Ver: [`patterns/saga-pattern.md`](./patterns/saga-pattern.md)

### Consistencia
- **Lecturas (Usuarios, Eventos):** Eventual consistency (caché Redis OK)
- **Escrituras (Reservas, Pagos):** Strong consistency (Redis atomic + validaciones)
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

- **Pre-defensa:** Jueves 5 de noviembre (~15 días)
- **Defensa final:** Jueves 12 de noviembre (~22 días)
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
R: Ver [`patterns/chain-of-responsibility-pattern.md`](./patterns/chain-of-responsibility-pattern.md) — cadena modular de validadores.

**P: ¿Cómo inicio los servicios?**  
R: Ver [`deployment/docker-compose.md`](./deployment/docker-compose.md) — `docker-compose up -d`

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
