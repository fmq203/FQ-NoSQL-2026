# Índice Master — EventFlow Brain

**Última actualización:** 2026-09-20

---

## 🎯 Decisiones Arquitectónicas

- [[db-selection]] — Bases de datos seleccionadas (MongoDB, Redis, PostgreSQL)
- [[three-database-strategy]] — Estrategia de 3 BDs + especialización
- [[consistency-strategy]] — Estrategia de consistencia (AP, CP, CA)
- [[deployment-strategy]] — Tecnologías de despliegue (Docker, Compose)

## 🏗️ Arquitectura

- [[architecture-overview]] — Vista general del sistema
- [[microservices-diagram]] — Diagrama de microservicios
- [[data-flow]] — Flujo de datos entre servicios
- [[saga-flow]] — Flujo del patrón SAGA (orquestación)
- [[chain-of-responsibility-diagram]] — Diagrama Chain of Responsibility

## 🔌 Microservicios

- [[usuarios-service]] — Servicio de Usuarios
- [[eventos-service]] — Servicio de Eventos
- [[reservas-pagos-service]] — Servicio de Reservas y Pagos

## 📡 APIs y Endpoints

- [[usuarios-endpoints]] — Endpoints del servicio de usuarios
- [[eventos-endpoints]] — Endpoints del servicio de eventos
- [[reservas-endpoints]] — Endpoints del servicio de reservas

## 💾 Modelos de Datos

- [[user-schema]] — Schema de Usuario (MongoDB)
- [[event-schema]] — Schema de Evento (MongoDB)
- [[reservation-schema]] — Schema de Reserva (Redis)
- [[event-log-schema]] — Schema de Event Log (PostgreSQL, append-only)
- [[db-rationale]] — Justificación MongoDB vs Redis vs PostgreSQL

## 🎯 Patrones de Diseño

- [[saga-pattern]] — Patrón SAGA: orquestación + compensación
- [[chain-of-responsibility-pattern]] — Validadores en cadena
- [[event-log-pattern]] — Event Log append-only (PostgreSQL)
- [[event-sourcing-cqrs]] — Event Sourcing y CQRS (opcional avanzado)

## 🐳 Despliegue & API Docs

- [[docker-setup]] — Configuración Docker y Dockerfiles
- [[docker-compose-config]] — docker-compose.yml template
- [[deployment-checklist]] — Checklist antes de desplegar
- [[spec-kit-setup]] — spec-kit para OpenAPI automático ✨
- [[openapi-template.json]] — Template OpenAPI 3.0.0
- [[spec-kit-code-example.py]] — Ejemplo de código con decoradores

## 📚 Aprendizajes

- [[learnings]] — Notas y decisiones fallidas

---

## 📌 Requerimientos Clave (del PDF)

### Consistencia y L/W
- ✅ Lectura eventos/usuarios: rápida, escalable (eventual consistency)
- ✅ Escritura reservas/pagos: alta consistencia (strong consistency)

### Tecnologías
- ✅ Mínimo 2 BDs NoSQL
- ✅ Python (FastAPI) / Spring Boot / Node (Express)
- ✅ Docker + Docker Compose / minikube
- ⚡ Opcional: JMeter, Event Sourcing, CQRS, anonimización

### Patrones Obligatorios
- ✅ SAGA con orquestación
- ✅ Chain of Responsibility

### Entregables
- ✅ README.md con justificación + diagramas
- ✅ Código en Git (estructura de carpetas)
- ✅ docker-compose.yml funcional
- ✅ Presentación ~12 min (pre-defensa 5 nov, final 12 nov)

---

**Próximo:** Empezar con [[db-selection]]
