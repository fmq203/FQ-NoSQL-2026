"""
Ejemplo: Usuarios Service con spec-kit decorators
Esto genera spec.json automáticamente desde los decoradores.

Ejecutar:
  pip install fastapi uvicorn spec-kit
  spec-kit generate --output spec.json
  uvicorn main:app --reload

Ver spec en http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

# ============ SPEC-KIT DECORADOR ============
# En producción, usar @spec_endpoint de spec-kit
# Para este ejemplo, usamos comentarios docstring que spec-kit parsea

# ============ MODELOS ============

class TipoDocumento(str, Enum):
    DNI = "DNI"
    PASAPORTE = "Pasaporte"

class UsuarioCreate(BaseModel):
    """Usuario a crear (request body)"""
    tipo_documento: TipoDocumento = Field(..., description="Tipo de documento")
    nro_documento: str = Field(..., description="Número de documento", example="12345678")
    nombre: str = Field(..., description="Nombre del usuario", example="Juan")
    apellido: str = Field(..., description="Apellido del usuario", example="Pérez")
    email: EmailStr = Field(..., description="Email único", example="juan@example.com")

class Usuario(UsuarioCreate):
    """Usuario completo (response)"""
    usuario_id: UUID = Field(..., description="ID único del usuario")
    creado_en: datetime = Field(..., description="Fecha de creación")
    historial_compras: List[dict] = Field(default_factory=list, description="Historial de compras")

class UsuarioAnonimizado(BaseModel):
    """Usuario con datos personales anonimizados (GDPR)"""
    usuario_hash: str = Field(..., description="Hash del usuario (irreversible)")
    eventos_comprados: int = Field(..., description="Cantidad de eventos comprados")
    gasto_total: float = Field(..., description="Gasto total acumulado")

class ErrorResponse(BaseModel):
    """Response de error estándar"""
    error: str = Field(..., description="Código de error")
    detalles: str = Field(..., description="Detalles del error")

# ============ APP ============

app = FastAPI(
    title="Usuarios Service",
    version="1.0.0",
    description="Gestión de usuarios y perfiles en EventFlow"
)

# ============ DEPENDENCIAS ============

async def verificar_usuario_existe(usuario_id: UUID):
    """Dependencia: verifica que usuario existe antes de procesar request"""
    # En producción: buscar en MongoDB
    return usuario_id

# ============ ENDPOINTS ============

@app.get("/health", tags=["System"])
async def health():
    """
    **Health Check**

    Verifica que el servicio está online y funcionando.

    Retorna:
    - status: "ok" si todo funciona
    """
    return {"status": "ok"}

@app.post(
    "/api/usuarios",
    response_model=Usuario,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Datos inválidos"},
        409: {"model": ErrorResponse, "description": "Email ya existe"}
    },
    tags=["Usuarios"]
)
async def crear_usuario(usuario: UsuarioCreate):
    """
    **POST /api/usuarios** — Crear nuevo usuario

    Crea un nuevo usuario en el sistema.

    Validaciones:
    - Email debe ser único
    - Nombre y email son obligatorios
    - Documento es único

    Retorna:
    - Usuario creado con ID único y timestamp

    Ejemplos de request:
    ```json
    {
      "tipo_documento": "DNI",
      "nro_documento": "12345678",
      "nombre": "Juan",
      "apellido": "Pérez",
      "email": "juan@example.com"
    }
    ```

    Respuesta (201):
    ```json
    {
      "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
      "nombre": "Juan",
      "email": "juan@example.com",
      "creado_en": "2026-09-20T10:00:00Z"
    }
    ```
    """
    # Lógica: validar email único
    # Lógica: crear en MongoDB

    nuevo_usuario = Usuario(
        usuario_id=uuid4(),
        **usuario.dict(),
        creado_en=datetime.utcnow(),
        historial_compras=[]
    )

    # db.usuarios.insert_one(nuevo_usuario.dict())

    return nuevo_usuario

@app.get(
    "/api/usuarios",
    response_model=List[Usuario],
    tags=["Usuarios"]
)
async def listar_usuarios(skip: int = 0, limit: int = 10):
    """
    **GET /api/usuarios** — Listar usuarios

    Retorna una lista paginada de usuarios.

    Query Parameters:
    - skip: número de registros a saltar (default: 0)
    - limit: máximo de registros a retornar (default: 10)

    Retorna:
    - Array de usuarios

    Ejemplo:
    ```
    GET /api/usuarios?skip=0&limit=20
    ```
    """
    # usuarios = db.usuarios.find().skip(skip).limit(limit)
    # return usuarios
    return []

@app.get(
    "/api/usuarios/{usuario_id}",
    response_model=Usuario,
    responses={
        404: {"model": ErrorResponse, "description": "Usuario no encontrado"}
    },
    tags=["Usuarios"]
)
async def obtener_usuario(
    usuario_id: UUID,
    usuario_verificado: UUID = Depends(verificar_usuario_existe)
):
    """
    **GET /api/usuarios/{usuario_id}** — Obtener usuario por ID

    Retorna los datos completos de un usuario específico, incluyendo historial.

    Path Parameters:
    - usuario_id: UUID del usuario (requerido)

    Retorna:
    - Usuario con historial de compras

    Errores:
    - 404: Usuario no encontrado

    Ejemplo:
    ```
    GET /api/usuarios/550e8400-e29b-41d4-a716-446655440000
    ```
    """
    # usuario = db.usuarios.findOne({"_id": usuario_id})
    # if not usuario:
    #     raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # return usuario
    pass

@app.get(
    "/api/usuarios/exportar",
    response_model=dict,
    tags=["Usuarios"]
)
async def exportar_usuarios(format: str = "json"):
    """
    **GET /api/usuarios/exportar** — Exportar usuarios (anonimizados)

    Exporta datos de usuarios con privacidad garantizada:
    - Nombres/emails/documentos: anonimizados irreversiblemente
    - Historial de eventos: PRESERVADO (para análisis)
    - Formato: JSON o CSV

    Query Parameters:
    - format: "json" | "csv" (default: "json")

    Requisitos GDPR:
    - ✅ Anonimización irreversible
    - ✅ Historial preservado (para compliance)
    - ✅ Sin datos personales identificables

    Retorna:
    ```json
    {
      "usuarios_anonimizados": [
        {
          "usuario_hash": "a1b2c3d4e5f6...",
          "eventos_comprados": 5,
          "gasto_total": 750.00
        }
      ]
    }
    ```
    """
    # usuarios = db.usuarios.find()
    # anonimizados = [
    #     {
    #         "usuario_hash": hash(u["_id"]),
    #         "eventos_comprados": len(u["historial_compras"]),
    #         "gasto_total": sum(c["precio"] for c in u["historial_compras"])
    #     }
    #     for u in usuarios
    # ]
    # return {"usuarios_anonimizados": anonimizados}
    return {"usuarios_anonimizados": []}

@app.get(
    "/api/usuarios/{usuario_id}/historial",
    response_model=List[dict],
    tags=["Usuarios"]
)
async def obtener_historial_usuario(usuario_id: UUID, limit: int = 10):
    """
    **GET /api/usuarios/{usuario_id}/historial** — Historial de compras

    Retorna el historial paginado de compras del usuario.

    Path Parameters:
    - usuario_id: UUID del usuario

    Query Parameters:
    - limit: máximo de registros (default: 10)

    Retorna:
    - Array de compras ordenadas por fecha descendente

    Campos por compra:
    - reserva_id: UUID
    - evento_id: UUID
    - cantidad: número de entradas
    - precio_total: monto
    - fecha_compra: timestamp
    - estado: "confirmada" | "cancelada"
    """
    # usuario = db.usuarios.findOne({"_id": usuario_id})
    # return usuario["historial_compras"][:limit]
    return []

# ============ ERROR HANDLERS ============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Maneja errores HTTP estándar"""
    return {
        "error": "http_error",
        "detalles": str(exc.detail),
        "status": exc.status_code
    }

# ============ GENERAR SPEC ============

# En terminal:
# spec-kit generate --output spec.json
#
# Esto parsea los docstrings y decoradores, genera spec.json (OpenAPI 3.0.0)
#
# Luego:
# - spec-kit validate (verifica que spec es válido)
# - spec-kit serve (sirve spec en http://localhost:8000/spec.json)
# - Swagger UI disponible en http://localhost:8000/docs
