---
name: spec-kit-setup
description: Cómo se usó Spec Kit (desarrollo guiado por especificaciones) y de dónde sale la OpenAPI
metadata:
  type: deployment
  status: complete
---

# Spec Kit y documentación de APIs

**Revisado 2026-11-05.** La primera versión de este archivo describía un "spec-kit" con decoradores que generaba `spec.json` desde el código. Eso no existe y no se usó. Lo que se usó es lo siguiente.

## 1. GitHub Spec Kit: desarrollo guiado por especificaciones

Spec Kit (`.specify/`, versión 1.0.9.dev0) es un flujo de trabajo para escribir la especificación **antes** del código y derivar de ella el plan y las tareas. Se usó con un agente de IA mediante comandos `/speckit.*`.

```
.specify/
├── memory/constitution.md          principios del proyecto
├── templates/                      spec, plan, tasks, checklist
└── specs/
    ├── 001-usuarios-crud/          spec.md + checklists
    ├── 002-eventos-crud/           spec, plan, research, data-model, contracts, quickstart, tasks
    └── 003-reservation-payment/    spec, plan, research, data-model, quickstart, tasks
```

Flujo por feature:

| Comando | Produce |
|---------|---------|
| `/speckit.specify` | `spec.md`: requisitos funcionales, criterios de éxito (p. ej. RP-SC-007: p99 < 1 s a 100 req/s) |
| `/speckit.plan` | `plan.md`, `research.md`, `data-model.md`, `contracts/` |
| `/speckit.tasks` | `tasks.md`: tareas ordenadas y testeables |
| `/speckit.analyze` | Inconsistencias entre spec, plan y tasks (se usó sobre 003; ver `learnings.md`) |
| `/speckit.implement` | Implementación guiada por `tasks.md` |

Los `spec.md` son la referencia de **qué** debía cumplir cada servicio; el brain documenta **cómo** quedó. Donde difieren, el código y este brain están revisados contra el código (2026-11-05).

## 2. OpenAPI: la genera FastAPI

No hay un archivo de especificación mantenido a mano: cada servicio expone la suya, generada desde las rutas y los modelos Pydantic.

| Servicio | OpenAPI | Swagger | ReDoc |
|----------|---------|---------|-------|
| Usuarios | http://localhost:8001/openapi.json | /docs | /redoc |
| Eventos | http://localhost:8002/openapi.json | /docs | /redoc |
| Reservas | http://localhost:8003/openapi.json | /docs | /redoc |

```bash
curl -s localhost:8003/openapi.json | jq '.paths | keys'
```

Los tests de contrato (`tests/contract/`) verifican que la spec generada documente los endpoints y las respuestas de error RFC 7807; en Eventos además se corre **schemathesis** contra la spec (genera requests a partir de ella y verifica que las respuestas la cumplan).

## Archivos relacionados en `brain/deployment/`

- `openapi-template.json` y `spec-kit-code-example.py`: bocetos de la etapa de diseño, **no** reflejan las APIs reales. Se conservan como historia; la fuente de verdad es `/openapi.json` de cada servicio.
