# EventFlow Brain — Second Brain para Tarea 2 NoSQL

**Rol:** Asistente especializado en diseño e implementación del sistema de microservicios **EventFlow** para gestión de eventos.

**Última actualización:** 2026-11-05 (brain completo revisado contra el código)  
**Fecha entrega pre-defensa:** 2026-11-05  
**Fecha entrega final:** 2026-11-12

---

## 📋 Directorio de Carpetas

### `decisions/`
Decisiones de diseño arquitectónico y justificaciones.
- **Inmutable:** El índice se actualiza cuando hay nuevas decisiones.
- **Dueño:** Equipo (se actualiza durante sesiones de diseño).
- Archivos: `db-selection.md`, `consistency-strategy.md`, `deployment-strategy.md`, etc.

### `architecture/`
Diagramas, esquemas y vista general del sistema.
- **Dueño:** Yo (Claude) + equipo (revisan y sugieren cambios).
- Contiene: `overview.md`, `microservices-diagram.md`, `data-flow.md`, `saga-flow.md` (la cadena está en `patterns/chain-of-responsibility.md`).

### `microservices/`
Especificación detallada de cada microservicio (Usuarios, Eventos, Reservas).
- **Dueño:** Equipo (yo actualizo esquemas y sumarizo).
- Estructura: `usuarios.md`, `eventos.md`, `reservas-pagos.md`.

### `endpoints/`
Especificación de APIs REST.
- **Fuente de verdad:** la OpenAPI que genera FastAPI en `http://localhost:800{1,2,3}/openapi.json` (Swagger en `/docs`).
- **Brain:** `*-endpoints.md` resume cada endpoint, errores y comportamiento (caché, idempotencia) que la spec no explica.

### `data-models/`
Schemas NoSQL, decisiones embed vs reference, modelos de datos.
- **Dueño:** Equipo + yo.
- Archivos: `user-schema.md`, `event-schema.md`, `reservation-schema.md`, `event-log-schema.md`, `db-choice-rationale.md`.

### `patterns/`
Implementación de patrones: SAGA (orquestación), Chain of Responsibility, Event Sourcing, CQRS.
- **Dueño:** Equipo (código) + yo (documenta patrones).
- Archivos: `saga-pattern.md`, `chain-of-responsibility.md`, `event-log-pattern.md`, `event-sourcing-cqrs.md`.

### `deployment/`
Docker, Docker Compose, variables de entorno, configuración (Kubernetes solo como diseño).
- **Dueño:** Equipo + yo.
- Archivos: `docker-setup.md`, `docker-compose.md`, `deployment-checklist.md`, `requirements.md`, `spec-kit-setup.md`, `postgresql-init.sql`; bocetos históricos `openapi-template.json`, `spec-kit-code-example.py`.

### `learnings/`
Notas, lecciones aprendidas, decisiones fallidas, insights técnicos.
- **Dueño:** Equipo (registra descubrimientos).
- Archivo: `learnings.md` (append-only).

---

## 📖 Protocolo de Lectura

**Al iniciar una sesión:**
1. Leo este archivo (CLAUDE.md) primero.
2. Consulto `index.md` para mapear qué existe.
3. Si la pregunta es sobre decisiones → leo `decisions/` primero.
4. Si es sobre implementación → voy a `microservices/` y `patterns/`.

---

## ✍️ Convenciones

### Estructura de Archivo
```markdown
---
name: nombre-kebab-case
description: Una línea descripción
metadata:
  type: decision | architecture | specification | pattern | learnings
  status: draft | in-progress | complete
---

# Título
Contenido...
```

### Formato
- **Decisiones:** Problema → Opciones → Decisión → Justificación.
- **Especificaciones:** Tablas de endpoints, schemas, campos requeridos.
- **Patrones:** Diagrama + flujo + código.

---

## 🚫 Restricciones

1. Nunca inventar datos — si falta info, preguntar al equipo.
2. Mantener CLAUDE.md bajo 200 líneas.
3. Links internos: `[[nombre-archivo]]`.

---

## 📝 Checklist

- [x] Decisiones de BD seleccionadas
- [x] Arquitectura diagrama completada
- [x] APIs especificadas
- [x] Data models decididos
- [x] Patrones SAGA + CoR documentados
- [x] Docker Compose funcional
- [x] Brain revisado contra el código (2026-11-05)
- [ ] Pre-defensa 2026-11-05
- [ ] Defensa final 2026-11-12
