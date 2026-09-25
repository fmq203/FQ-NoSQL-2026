"""
Modelos de dominio para Usuarios Service.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class TipoDocumento(str, Enum):
    DNI = "DNI"
    PASAPORTE = "Pasaporte"


class UsuarioBase(BaseModel):
    """Campos base del usuario."""
    tipo_documento: TipoDocumento
    nro_documento: str = Field(..., min_length=1, max_length=50)
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    """Datos para crear un usuario."""
    pass


class HistorialCompra(BaseModel):
    """Historial de compras del usuario."""
    evento_id: UUID
    evento_nombre: str
    fecha_compra: datetime
    entradas: int
    total_pagado: float
    estado: str


class UsuarioResponse(UsuarioBase):
    """Respuesta completa de usuario."""
    usuario_id: UUID
    creado_en: datetime
    actualizado_en: datetime
    historial_compras: List[HistorialCompra] = []

    class Config:
        from_attributes = True


class UsuarioAnonimizado(BaseModel):
    """Usuario con datos anonimizados para exportación GDPR."""
    usuario_id_hash: str
    tipo_documento: TipoDocumento
    nro_documento_hash: str
    nombre_hash: str
    apellido_hash: str
    email_hash: str
    creado_en: datetime
    historial_compras: List[HistorialCompra] = []