# EventFlow Constitution

## Core Principles

### I. Microservice Autonomy
Each microservice (Usuarios, Eventos, Reservas) is independently deployable, testable, and owns its data. No shared databases between services. Communication via well-defined HTTP/REST contracts.

### II. API-First Contract
All service interfaces defined via OpenAPI 3.1 (auto-generated from FastAPI). Specs are the source of truth. Breaking changes require versioning and migration plan.

### III. Test-First (NON-NEGOTIABLE)
TDD mandatory: Contract tests → Integration tests → Unit tests. Tests written → User approved → Tests fail → Then implement. Red-Green-Refactor cycle strictly enforced. Minimum 80% coverage on business logic.

### IV. Observability by Default
Structured logging (JSON) on all services. Health checks (`/health`) on every service. Distributed tracing via correlation IDs. Metrics: latency, error rate, throughput per endpoint.

### V. Polyglot Persistence with Justification
Database choice per service documented with rationale (see `brain/decisions/db-selection.md`). No default database. Embedded vs Reference patterns explicitly decided per entity.

### VI. Distributed Transactions via SAGA
Multi-service operations use SAGA Orchestration (Reservas Service as orchestrator). Compensating transactions for every mutating step. No 2PC / distributed locks.

### VII. Security & Privacy by Design
GDPR compliance: Anonymization endpoint with irreversible hashing. No PII in logs. Input validation at API boundary. Secrets via environment variables only.

### VIII. Simplicity & YAGNI
Start with simplest implementation. Avoid premature abstraction. No frameworks not justified by requirements. Configuration over convention.

## Technology Stack Constraints

- **Language**: Python 3.11 (FastAPI, Uvicorn)
- **Databases**: MongoDB 7.0, Redis 7.0, PostgreSQL 15
- **Containerization**: Docker + Docker Compose (dev), K8s-ready (prod)
- **Testing**: pytest, pytest-asyncio, httpx for contract tests
- **Documentation**: OpenAPI/Swagger auto-generated, Markdown specs

## Development Workflow

1. **Spec** → `/speckit.specify` creates `spec.md` from requirements
2. **Plan** → `/speckit.plan` creates `plan.md` with technical approach
3. **Tasks** → `/speckit.tasks` creates `tasks.md` with implementation steps
4. **Implement** → `/speckit.implement` executes tasks
5. **Converge** → `/speckit.converge` validates codebase vs spec

## Quality Gates

- All contract tests pass (OpenAPI compliance)
- Integration tests pass (service-to-service)
- Health checks pass on all services
- Docker compose builds without errors
- No critical vulnerabilities in dependencies

## Governance

Constitution supersedes all other practices. Amendments require:
1. Documentation of change and rationale
2. Team approval
3. Migration plan for existing code

**Version**: 1.0.0 | **Ratified**: 2026-09-20 | **Last Amended**: 2026-09-20