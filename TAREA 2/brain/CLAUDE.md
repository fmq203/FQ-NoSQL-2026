# EventFlow Brain — Second Brain para Tarea 2 NoSQL

**Rol:** Asistente especializado en diseño e implementación del sistema de microservicios **EventFlow** para gestión de eventos.

**Última actualización:** 2026-09-20  
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
- Contiene: `overview.md`, `microservices-diagram.md`, `data-flow.md`, `saga-flow.md`, `chain-of-responsibility.md`.

### `microservices/`
Especificación detallada de cada microservicio (Usuarios, Eventos, Reservas).
- **Dueño:** Equipo (yo actualizo esquemas y sumarizo).
- Estructura: `usuarios.md`, `eventos.md`, `reservas-pagos.md`.

### `endpoints/`
Especificación de APIs REST (referencias a spec-kit OpenAPI).
- **Dueño:** spec-kit genera spec.json automáticamente desde código.
- **Brain referencia:** `usuarios-endpoints.md` → punto a `/spec.json` (no duplica).
- **Fuente de verdad:** `/usuarios-service/spec.json` (generado automáticamente).

### `data-models/`
Schemas NoSQL, decisiones embed vs reference, modelos de datos.
- **Dueño:** Equipo + yo.
- Archivos: `user-schema.md`, `event-schema.md`, `reservation-schema.md`, `db-choice-rationale.md`.

### `patterns/`
Implementación de patrones: SAGA (orquestación), Chain of Responsibility, Event Sourcing, CQRS.
- **Dueño:** Equipo (código) + yo (documenta patrones).
- Archivos: `saga-pattern.md`, `chain-of-responsibility.md`, `event-sourcing-cqrs.md`.

### `deployment/`
Docker, Docker Compose, Kubernetes, variables de entorno, configuración.
- **Dueño:** Equipo + yo (mantengo templates).
- Archivos: `docker-setup.md`, `docker-compose.md`, `deployment-checklist.md`.

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

- [ ] Decisiones de BD seleccionadas
- [ ] Arquitectura diagrama completada
- [ ] APIs especificadas
- [ ] Data models decididos
- [ ] Patrones SAGA + CoR documentados
- [ ] Docker Compose funcional
- [ ] Pre-defensa 2026-11-05
- [ ] Defensa final 2026-11-12
