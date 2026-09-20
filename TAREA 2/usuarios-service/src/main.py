"""
Usuarios Service - EventFlow

Gestión de usuarios y perfiles.

Ver documentación:
- brain/microservices/usuarios.md
- brain/deployment/spec-kit-code-example.py
- brain/endpoints/usuarios-endpoints.md
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
import os
from pymongo import MongoClient
from enum import Enum

# ============ CONFIGURACIÓN ============

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "eventflow")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", 8001))

# ============ INICIALIZAR APP ============

app = FastAPI(
    title="Usuarios Service",
    version="1.0.0",
    description="Gestión de usuarios y perfiles en EventFlow"
)

# ============ MODELOS ============

class TipoDocumento(str, Enum):
    DNI = "DNI"
    PASAPORTE = "Pasaporte"

class UsuarioCreate(BaseModel):
    """Usuario a crear (request body)"""
    tipo_documento: TipoDocumento
    nro_documento: str
    nombre: str
    apellido: str
    email: EmailStr

class Usuario(UsuarioCreate):
    """Usuario completo (response)"""
    usuario_id: UUID
    creado_en: datetime

# ============ DEPENDENCIAS ============

def get_db():
    """Conectar a MongoDB"""
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    return db

# ============ ENDPOINTS ============

@app.get("/health")
async def health():
    """Health check - verifica que el servicio está online"""
    return {"status": "ok", "service": "usuarios"}

@app.post("/api/usuarios", response_model=Usuario, status_code=201)
async def crear_usuario(usuario: UsuarioCreate, db = Depends(get_db)):
    """
    Crear nuevo usuario

    Validaciones:
    - Email debe ser único
    - Nombre y email son obligatorios

    Retorna usuario creado con ID único
    """
    # TODO: Implementar
    # 1. Verificar que email no existe
    # 2. Crear documento en MongoDB
    # 3. Retornar usuario creado

    return Usuario(
        usuario_id=uuid4(),
        **usuario.dict(),
        creado_en=datetime.utcnow()
    )

@app.get("/api/usuarios")
async def listar_usuarios(skip: int = 0, limit: int = 10, db = Depends(get_db)):
    """
    Listar usuarios (paginado)

    Query Parameters:
    - skip: saltar N registros
    - limit: máximo de registros a retornar
    """
    # TODO: Implementar
    # 1. Buscar en MongoDB con skip/limit
    # 2. Retornar lista

    return []

@app.get("/api/usuarios/{usuario_id}", response_model=Usuario)
async def obtener_usuario(usuario_id: UUID, db = Depends(get_db)):
    """
    Obtener usuario por ID

    Incluye historial de compras
    """
    # TODO: Implementar
    # 1. Buscar en MongoDB por _id
    # 2. Si no existe, retornar 404
    # 3. Retornar usuario

    raise HTTPException(status_code=404, detail="Usuario no encontrado")

@app.get("/api/usuarios/exportar")
async def exportar_usuarios(format: str = "json", db = Depends(get_db)):
    """
    Exportar usuarios anonimizados (GDPR)

    - Nombres/emails: anonimizados irreversiblemente
    - Historial: preservado para análisis
    """
    # TODO: Implementar
    # 1. Obtener todos los usuarios
    # 2. Anonimizar datos personales (hash irreversible)
    # 3. Mantener historial de eventos
    # 4. Retornar en formato JSON o CSV

    return {"usuarios_anonimizados": []}

# ============ STARTUP/SHUTDOWN ============

@app.on_event("startup")
async def startup():
    """Inicialización al arrancar el servicio"""
    print(f"✅ Usuarios Service iniciado en puerto {SERVICE_PORT}")
    # TODO: Verificar conexión a MongoDB
    # TODO: Crear índices en BD

@app.on_event("shutdown")
async def shutdown():
    """Limpieza al apagar el servicio"""
    print("👋 Usuarios Service detenido")

# ============ MAIN ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)

# ============ SPEC-KIT ============
# Para generar spec.json:
# spec-kit generate --output spec.json
#
# Para ver docs:
# http://localhost:8001/docs
