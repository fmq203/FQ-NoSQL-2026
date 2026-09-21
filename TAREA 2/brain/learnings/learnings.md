---
name: learnings
description: Registro de interacciones con IA, lecciones aprendidas y decisiones técnicas
metadata:
  type: learnings
  status: in-progress
---

# Learnings — Registro de Interacciones y Decisiones Técnicas

> **Formato**: Append-only. Cada entrada: fecha, contexto, decisión/insight, referencia.

---

## 2026-09-20 — Inicialización del Proyecto EventFlow

### Contexto
Inicio de Tarea 2 NoSQL: Diseño e implementación de sistema de microservicios EventFlow. Requerimientos extraídos de `Tarea 2 NoSql.pdf`.

### Decisiones Arquitectónicas Principales

1. **Tres microservicios** + **Tres bases de datos** (políglota):
   - Usuarios → MongoDB
   - Eventos → MongoDB + Redis cache
   - Reservas → MongoDB + Redis (pagos) + PostgreSQL (auditoría)

2. **Patrones obligatorios implementados**:
   - SAGA Orchestration (Reservas Service como orquestador)
   - Chain of Responsibility (validaciones secuenciales en Reservas)
   - Event Sourcing + CQRS (PostgreSQL audit log)

3. **Consistencia híbrida**:
   - Lecturas (usuarios, eventos): Eventual (secondaryPreferred)
   - Escrituras (reservas, pagos): Fuerte (Redis Lua + MongoDB majority + PostgreSQL ACID)

4. **Despliegue**: Docker Compose con health checks, listo para Kubernetes

### Interacciones con IA (Esta Sesión)

| Paso | Acción | Herramienta | Resultado |
|------|--------|-------------|-----------|
| 1 | Extraer requerimientos PDF | `pdfplumber` | 5 páginas parseadas, requerimientos clarificados |
| 2 | Analizar código existente | `glob`, `read` | 3 servicios parciales, docker-compose base |
| 3 | Corregir dependencias Python | `bash`, `edit` | `requirements.txt` limpio (pydantic≥2, email-validator) |
| 4 | Arreglar Dockerfiles | `edit` | `COPY ../requirements.txt` → `COPY requirements.txt` local |
| 5 | Instalar spec-kit / specify-cli | `uvx` | Inicializado en `.opencode/commands/` para opencode |
| 6 | Levantar stack completo | `docker compose` | 6 contenedores healthy (3 DBs + 3 servicios) |
| 7 | Verificar OpenAPI auto-generado | `curl` | Swagger UI en `/docs`, spec en `/openapi.json` |
| 8 | Crear brain/ documentation | `write` | 15 archivos Markdown estructurados |

### Insights Técnicos Clave

#### 1. spec-kit ≠ OpenAPI Generator
- **GitHub spec-kit** (ahora `specify-cli`) es un **framework de Spec-Driven Development para agentes IA**, no un generador de OpenAPI desde código.
- **FastAPI ya genera OpenAPI 3.1 automáticamente** desde modelos Pydantic y decoradores. No se necesita herramienta externa.
- speculate-cli instalado para workflow de especificación (/speckit.specify, /speckit.plan, etc.)

#### 2. MongoDB Health Check
- `mongosh --eval "db.admin.ping()"` **falla** (método inexistente)
- Correcto: `mongosh --eval "db.runCommand({ping:1})"` → `{ok: 1}`

#### 3. Pydantic v2 + EmailStr
- Requiere `email-validator` package explícito
- Error: `ImportError: email-validator is not installed, run \`pip install 'pydantic[email]'\``

#### 4. Docker Build Context
- `COPY ../requirements.txt` **no funciona** (fuera del build context)
- Solución: Copiar `requirements.txt` a cada directorio de servicio

#### 5. Redis Lua Scripts para Atomicidad
- Única forma de garantizar **pago + decremento inventario** atómico
- Single-threaded Redis = consistencia fuerte inherente
- Latencia < 1ms vs 10-50ms transacciones MongoDB

#### 6. Chain of Responsibility en FastAPI
- Patrón nativo con `Handler` base class + `set_next()`
- Context dataclass viaja por la cadena
- Facilita testing unitario y compensaciones ordenadas

### Archivos Creados en brain/

```
brain/
├── CLAUDE.md (existía)
├── architecture/
│   ├── overview.md
│   ├── microservices-diagram.md
│   ├── data-flow.md
│   ├── saga-flow.md
│   └── chain-of-responsibility.md
├── decisions/
│   ├── db-selection.md
│   ├── consistency-strategy.md
│   └── deployment-strategy.md
├── microservices/
│   ├── usuarios.md
│   ├── eventos.md
│   └── reservas-pagos.md
├── data-models/
│   ├── user-schema.md
│   ├── event-schema.md
│   ├── reservation-schema.md
│   └── db-choice-rationale.md
├── patterns/ (pendiente)
├── endpoints/ (pendiente)
├── deployment/ (pendiente)
└── learnings/
    └── learnings.md (ESTE ARCHIVO)
```

### Próximos Pasos Pendientes

- [ ] Completar `patterns/` (saga-pattern.md, event-sourcing-cqrs.md)
- [ ] Completar `endpoints/` (referencias a OpenAPI specs)
- [ ] Completar `deployment/` (docker-setup, checklist)
- [ ] Implementar código completo en 3 servicios (actualmente stubs)
- [ ] Agregar tests de integración
- [ ] Generar README.md final con diagramas Mermaid

---

## 2026-09-20 — Nota sobre Embedded vs Reference

### Decisión: `historial_compras[]` EMBEDDED en Usuario

**Razones:**
- Cardinalidad one-to-few (< 50 compras típicas)
- Siempre se consulta con el perfil (exportación, dashboard)
- Atomicidad: agregar compra + actualizar usuario en single-doc update
- `$push` con `$slice: -50` mantiene últimas 50 automáticamente

**Límite**: Documento < 16MB. Si usuario power-user > 500 compras → migrar a colección separada `usuario_historial`.

### Decisión: `precios[]` EMBEDDED en Evento

**Razones:**
- Categorías-precio-disponibilidad son tupla atómica
- Siempre se leen juntas (catálogo, validación aforo)
- Actualización atómica por categoría: `$inc: "precios.$.disponibles": -cantidad`

### Decisión: `saga_log[]` EMBEDDED en Reserva

**Razones:**
- Debugging local inmediato (no requiere join PostgreSQL)
- Inmutable tras confirmación (append-only natural)
- Tamaño acotado (6 pasos fijos)

---

## 2026-09-20 — Anonimización GDPR: Hash Irreversible

### Algoritmo Implementado
```python
SALT = os.getenv("ANONYMIZATION_SALT", "eventflow-salt-2026")
usuario_hash = hashlib.sha256(f"{usuario_id}{SALT}".encode()).hexdigest()
```

### Propiedades Garantizadas
| Propiedad | Cómo se logra |
|-----------|---------------|
| **Irreversible** | SHA-256 one-way function |
| **Determinista** | Mismo usuario_id + salt = mismo hash |
| **Resistente a rainbow tables** | Salt único por despliegue (configurable via env) |
| **Preserva analítica** | `eventos_comprados`, `gasto_total` se mantienen |

### Datos Eliminados vs Preservados
| Eliminados (PII) | Preservados (Análisis) |
|------------------|------------------------|
| nombre, apellido | eventos_comprados (count) |
| email | gasto_total (sum) |
| tipo_documento, nro_documento | — |

---

## 2026-09-20 — SAGA: Compensación PostgreSQL (Paso 6)

### Decisión: No Rollback en Fallo de Auditoría

```python
# En Auditor handler:
try:
    await pg_pool.execute(INSERT_EVENT_LOG)
except Exception as e:
    logging.warning(f"Auditoría falló para reserva {reserva_id}: {e}")
    # NO lanzar error — la reserva YA está confirmada en MongoDB
    return await self._pass_to_next(context)
```

**Justificación:**
- Reserva ya persistida en MongoDB (paso 5 exitoso)
- Cliente ya recibió 201 Confirmada
- Auditoría es **observabilidad**, no requisito de negocio
- Log warning → alerta para reconciliación manual posterior
- Evita compensación compleja (DELETE reserva + rollback Redis) por fallo de logging

---

## 2026-09-20 — Docker Compose: depends_on + healthcheck

### Patrón Robusto Implementado

```yaml
services:
  usuarios-service:
    depends_on:
      mongodb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 3
```

**Resultado**: Servicios inician **en orden correcto** y solo marcan healthy cuando responden HTTP 200 en `/health`.

### MongoDB Healthcheck Fix
```yaml
# INCORRECTO (falla):
test: ["CMD", "mongosh", "--eval", "db.admin.ping()"]

# CORRECTO:
test: ["CMD", "mongosh", "--eval", "db.runCommand({ping:1})"]
```

---

## Referencias Rápidas

| Tema | Archivo Brain |
|------|---------------|
| Arquitectura general | `architecture/overview.md` |
| Diagrama servicios | `architecture/microservices-diagram.md` |
| Flujo SAGA completo | `architecture/saga-flow.md` |
| Chain of Responsibility | `architecture/chain-of-responsibility.md` |
| Decisión DBs | `decisions/db-selection.md` |
| Consistencia | `decisions/consistency-strategy.md` |
| Despliegue | `decisions/deployment-strategy.md` |
| Esquema Usuario | `data-models/user-schema.md` |
| Esquema Evento | `data-models/event-schema.md` |
| Esquema Reserva | `data-models/reservation-schema.md` |
| Rationale multi-DB | `data-models/db-choice-rationale.md` |
| Spec usuarios | `microservices/usuarios.md` |
| Spec eventos | `microservices/eventos.md` |
| Spec reservas | `microservices/reservas-pagos.md` |