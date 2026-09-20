---
name: spec-kit-setup
description: Configuración de GitHub spec-kit para documentación automática de APIs
metadata:
  type: specification
  status: in-progress
---

# spec-kit Setup — OpenAPI Automático

## ¿Qué es spec-kit?

**spec-kit** es un toolkit de GitHub que:
- ✅ Genera OpenAPI specs automáticamente desde decoradores en código
- ✅ Valida requests/responses contra spec
- ✅ Genera mock servers
- ✅ Mantiene spec sincronizado con código (single source of truth)

---

## Instalación

```bash
npm install -g @github/spec-kit
# o
yarn add @github/spec-kit
```

---

## Estructura por Servicio

Cada microservicio tiene:

```
usuarios-service/
├── spec-kit.yml              ← Configuración
├── spec.json                 ← OpenAPI generado (DO NOT EDIT)
├── src/
│   ├── main.py
│   ├── routes.py             ← Código + decoradores
│   └── decorators.py         ← @api_endpoint decorators
└── tests/
    └── test_endpoints.py     ← Tests validan contra spec
```

---

## spec-kit.yml (Configuración)

```yaml
# usuarios-service/spec-kit.yml

openapi: '3.0.0'
info:
  title: Usuarios Service
  version: 1.0.0
  description: Gestión de usuarios y perfiles

servers:
  - url: http://localhost:8001
    description: Local

paths:
  /api/usuarios:
    post:
      summary: Crear nuevo usuario
      operationId: crear_usuario
      tags:
        - Usuarios
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UsuarioCreate'
      responses:
        '201':
          description: Usuario creado exitosamente
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Usuario'
        '400':
          description: Datos inválidos

    get:
      summary: Listar usuarios
      operationId: listar_usuarios
      tags:
        - Usuarios
      responses:
        '200':
          description: Lista de usuarios
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Usuario'

  /api/usuarios/{usuario_id}:
    get:
      summary: Obtener usuario por ID
      operationId: obtener_usuario
      tags:
        - Usuarios
      parameters:
        - name: usuario_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Usuario encontrado
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Usuario'
        '404':
          description: Usuario no encontrado

components:
  schemas:
    Usuario:
      type: object
      properties:
        usuario_id:
          type: string
          format: uuid
        tipo_documento:
          type: string
          enum: [DNI, Pasaporte]
        nro_documento:
          type: string
        nombre:
          type: string
        apellido:
          type: string
        email:
          type: string
          format: email
        creado_en:
          type: string
          format: date-time
      required:
        - usuario_id
        - nombre
        - email

    UsuarioCreate:
      type: object
      properties:
        tipo_documento:
          type: string
        nro_documento:
          type: string
        nombre:
          type: string
        apellido:
          type: string
        email:
          type: string
      required:
        - nombre
        - email
```

---

## Código con Decoradores (Python FastAPI)

```python
# usuarios-service/src/routes.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from spec_kit import spec_endpoint

app = FastAPI(
    title="Usuarios Service",
    version="1.0.0",
    description="Gestión de usuarios y perfiles"
)

# ============ MODELOS ============

class UsuarioCreate(BaseModel):
    tipo_documento: str = Field(..., example="DNI")
    nro_documento: str = Field(..., example="12345678")
    nombre: str = Field(..., example="Juan")
    apellido: str = Field(..., example="Pérez")
    email: str = Field(..., example="juan@example.com")

class Usuario(UsuarioCreate):
    usuario_id: UUID
    creado_en: datetime

# ============ ENDPOINTS ============

@app.post("/api/usuarios", status_code=201, response_model=Usuario)
@spec_endpoint(
    operationId="crear_usuario",
    summary="Crear nuevo usuario",
    tags=["Usuarios"]
)
async def crear_usuario(usuario: UsuarioCreate):
    """
    Crea un nuevo usuario en el sistema.
    
    - **tipo_documento**: DNI o Pasaporte
    - **nombre**: Nombre del usuario
    - **email**: Email único
    """
    # Lógica de creación...
    return Usuario(
        usuario_id=uuid4(),
        **usuario.dict(),
        creado_en=datetime.now()
    )

@app.get("/api/usuarios", response_model=List[Usuario])
@spec_endpoint(
    operationId="listar_usuarios",
    summary="Listar todos los usuarios",
    tags=["Usuarios"]
)
async def listar_usuarios(skip: int = 0, limit: int = 10):
    """
    Retorna una lista de usuarios paginada.
    """
    # Lógica de listado...
    return []

@app.get("/api/usuarios/{usuario_id}", response_model=Usuario)
@spec_endpoint(
    operationId="obtener_usuario",
    summary="Obtener usuario por ID",
    tags=["Usuarios"]
)
async def obtener_usuario(usuario_id: UUID):
    """
    Obtiene los datos de un usuario específico.
    
    - **usuario_id**: UUID del usuario
    
    Retorna 404 si no existe.
    """
    # Lógica de obtención...
    # raise HTTPException(status_code=404, detail="Usuario no encontrado")
    pass

# ============ HEALTH CHECK ============

@app.get("/health")
@spec_endpoint(
    summary="Health check",
    tags=["System"]
)
async def health():
    """Verifica que el servicio está online."""
    return {"status": "ok"}
```

---

## Generar spec.json desde código

```bash
cd usuarios-service

# Generar spec.json automáticamente
spec-kit generate --output spec.json

# Validar spec contra código
spec-kit validate

# Servir spec en http://localhost:8001/spec.json
spec-kit serve
```

---

## Integración con Docker

```dockerfile
# usuarios-service/Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Instalar spec-kit
RUN npm install -g @github/spec-kit

COPY src/ .

# Generar spec.json durante build
RUN spec-kit generate --output spec.json

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Validación en CI/CD

```bash
#!/bin/bash
# scripts/validate-specs.sh

for service in usuarios-service eventos-service reservas-service; do
  echo "Validando $service..."
  cd $service
  
  # Generar spec
  spec-kit generate --output spec.json
  
  # Validar
  spec-kit validate
  
  # Asegurar que spec.json existe
  if [ ! -f spec.json ]; then
    echo "❌ Error: spec.json no generado para $service"
    exit 1
  fi
  
  echo "✅ $service OK"
  cd ..
done
```

---

## Endpoints Públicos (Auto-documentados)

Cada servicio expone:

```
GET  /spec.json         ← OpenAPI spec (máquina readable)
GET  /docs              ← Swagger UI (humano readable)
GET  /redoc             ← ReDoc (alternativa)
GET  /health            ← Health check
```

**Ejemplo:**
```
http://localhost:8001/docs          → Swagger UI interactivo
http://localhost:8001/spec.json     → OpenAPI spec JSON
```

---

## Brain + spec-kit: Relación

```
Brain (Arquitectura & Decisiones)
  └─ `endpoints/` ahora referencia spec.json
     (no duplica)

spec-kit (OpenAPI Specs)
  └─ Generado automáticamente desde código
     └─ Validado en CI/CD
        └─ Disponible en /docs y /spec.json

Código (Implementación)
  └─ Decoradores @spec_endpoint
     └─ Genera spec.json automáticamente
        └─ Tests validan contra spec
```

---

## Workflow Recomendado

1. **Developer escribe código** con decoradores `@spec_endpoint`
2. **spec-kit genera spec.json** automáticamente
3. **CI/CD valida spec** (spec-kit validate)
4. **Swagger UI** disponible en `/docs`
5. **Brain referencia spec.json** (no duplica endpoints/)
6. **Tests validan requests/responses** contra spec

---

## Próximos Pasos

- [ ] Instalar spec-kit en cada servicio
- [ ] Crear spec-kit.yml base para cada servicio
- [ ] Agregar decoradores en código Python/Java/Node
- [ ] Validar en CI/CD
- [ ] Actualizar endpoints/ del brain (referencias en lugar de specs completas)
