---
name: usuarios-endpoints
description: Especificación de endpoints para Servicio de Usuarios (spec-kit)
metadata:
  type: specification
  status: draft
---

# Endpoints — Servicio de Usuarios

## 🔗 Fuente de Verdad: spec-kit

**IMPORTANTE:** Los endpoints se definen en `spec.json` (generado automáticamente desde código).

Este documento es una **referencia rápida**. Para la spec completa y actualizada:

1. **OpenAPI spec:** `/usuarios-service/spec.json`
2. **Swagger UI (interactivo):** `http://localhost:8001/docs`
3. **ReDoc (legible):** `http://localhost:8001/redoc`

---

## 🔄 Flujo de spec-kit

```
Code (Python FastAPI + decoradores)
    ↓ (spec-kit generate)
spec.json (OpenAPI 3.0.0)
    ↓
Swagger UI en /docs (automático)
```

**No duplicamos specs en Markdown** — spec.json es single source of truth.

## ✅ Endpoints Disponibles

Todos estos endpoints están definidos en `spec.json` y se pueden probar en:

- **Swagger UI:** http://localhost:8001/docs
- **OpenAPI JSON:** http://localhost:8001/spec.json

### POST /api/usuarios
Crear nuevo usuario

**Código generador:** [[spec-kit-code-example.py]] línea 62

---

### GET /api/usuarios
Listar usuarios (paginado)

**Query params:** `skip=0&limit=10`

**Código generador:** [[spec-kit-code-example.py]] línea 90

---

### GET /api/usuarios/{usuario_id}
Obtener usuario por ID

**Path params:** `usuario_id` (UUID)

**Código generador:** [[spec-kit-code-example.py]] línea 108

---

### GET /api/usuarios/{usuario_id}/historial
Historial de compras del usuario

**Query params:** `limit=10`

**Código generador:** [[spec-kit-code-example.py]] línea 152

---

### GET /api/usuarios/exportar
Exportar usuarios anonimizados (GDPR)

**Query params:** `format=json|csv`

**Código generador:** [[spec-kit-code-example.py]] línea 128

---

## 🔍 Cómo Probar

```bash
# 1. Generar spec desde código
cd usuarios-service
spec-kit generate --output spec.json

# 2. Iniciar servidor
uvicorn src.main:app --reload

# 3. Ir a Swagger UI
open http://localhost:8001/docs

# 4. Probar endpoints interactivamente en Swagger
```

---

## 📊 Validación en CI/CD

```bash
# En pipeline CI (GitHub Actions, GitLab CI, etc)
spec-kit validate  # Asegura spec.json es válido
spec-kit generate  # Regenera desde código
```

**Beneficio:** Spec siempre sincronizado con código (no hay divergencias)

---

## 🎯 Referencia Cruzada

- **Implementación:** [[spec-kit-code-example.py]]
- **Setup:** [[spec-kit-setup.md]]
- **Template OpenAPI:** [[openapi-template.json]]
- **Docker:** spec-kit se integra en Dockerfile (genera spec.json al build)
