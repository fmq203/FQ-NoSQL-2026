# Índice Master — EventFlow Brain

**Última actualización:** 2026-11-05 (todo el brain revisado contra el código)

Los enlaces `[[nombre]]` usan el nombre del archivo sin extensión.

---

## 🎯 Decisiones Arquitectónicas (`decisions/`)

- [[db-selection]] — Bases de datos seleccionadas (MongoDB, Redis, PostgreSQL) y asignación a servicios
- [[three-database-strategy]] — Qué guarda cada base y cómo colaboran en una compra
- [[consistency-strategy]] — Consistencia por operación (AP en lecturas, fuerte en la compra); estado real (un nodo)
- [[deployment-strategy]] — Docker Compose (implementado); Kubernetes (solo diseño)

## 🏗️ Arquitectura (`architecture/`)

- [[overview]] — Vista general: servicios, bases, patrones, endpoints
- [[microservices-diagram]] — Topología e interacciones
- [[data-flow]] — Secuencias: compra, lectura con caché, export
- [[saga-flow]] — SAGA paso a paso, Lua real, compensaciones y errores

## 🔌 Microservicios (`microservices/`)

- [[usuarios]] — Usuarios: perfil, historial embebido, export anonimizado, caché
- [[eventos]] — Eventos: precios por categoría, inventario, caché
- [[reservas-pagos]] — Reservas: orquestador SAGA + Chain of Responsibility

## 📡 APIs y Endpoints (`endpoints/`)

- [[usuarios-endpoints]]
- [[eventos-endpoints]]
- [[reservas-endpoints]]

## 💾 Modelos de Datos (`data-models/`)

- [[user-schema]] — `eventflow.usuarios`
- [[event-schema]] — `eventflow.eventos` + inventario Redis ↔ MongoDB
- [[reservation-schema]] — `eventflow.reservas`, claves Redis, payloads del event_log
- [[event-log-schema]] — Tabla `event_log`, consultas, vistas
- [[db-choice-rationale]] — Justificación por entidad

## 🎯 Patrones (`patterns/`)

- [[saga-pattern]] — Por qué SAGA orquestada, idempotencia
- [[chain-of-responsibility]] — Los 6 handlers (código real)
- [[event-log-pattern]] — Escritura append-only no bloqueante
- [[event-sourcing-cqrs]] — Event sourcing de auditoría + vistas CQRS (y qué no se implementó)

## 🐳 Despliegue (`deployment/`)

- [[docker-setup]] — Dockerfiles y dependencias
- [[docker-compose]] — docker-compose.yml real y variables
- [[deployment-checklist]] — Qué está verificado y qué faltaría para producción
- [[requirements]] — Qué se necesita para correrlo
- [[spec-kit-setup]] — Cómo se usó Spec Kit; de dónde sale la OpenAPI
- `postgresql-init.sql` — Copia de referencia del esquema que crea Reservas
- `openapi-template.json`, `spec-kit-code-example.py` — Bocetos históricos de diseño (no reflejan el código)

## 📚 Aprendizajes

- [[learnings]] — Registro cronológico (append-only) de decisiones, problemas e interacciones con IA

---

## 📌 Requerimientos Clave (del PDF) — estado

| Requerimiento | Estado |
|---------------|--------|
| Lectura usuarios/eventos rápida y disponible (eventual) | ✅ Caché AP stale-if-error (sin replica set) |
| Escritura reservas/pagos con consistencia fuerte | ✅ Lua atómico + idempotencia + SAGA; JMeter: sin doble venta |
| Mínimo 2 BDs NoSQL | ✅ MongoDB + Redis (+ PostgreSQL relacional) |
| Python / FastAPI, Docker Compose | ✅ |
| SAGA con orquestación, Chain of Responsibility | ✅ |
| Opcionales: JMeter, Event Sourcing, CQRS, anonimización | ✅ (Event sourcing de auditoría; JMeter muestra que la compra satura en ≈ 50 req/s) |
| README con justificación + diagramas, código en Git | ✅ |
| Presentación ~12 min (pre-defensa 5 nov, final 12 nov) | Demo en `demo/` |
