"""
Modelos de dominio para Usuarios Service.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
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

    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, value: str) -> str:
        """Normaliza a minúsculas: evita que 'A@x.com'/'a@x.com' se traten
        como emails distintos para la verificación de unicidad
        (usuario_service.py::crear_usuario)."""
        return value.lower()


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
    reserva_id: Optional[UUID] = None


class CompraRegistrar(BaseModel):
    """Body de POST /api/usuarios/{id}/historial (uso interno: lo llama
    reservas-service cuando una reserva queda confirmada)."""
    reserva_id: UUID
    evento_id: UUID
    evento_nombre: str = Field(..., min_length=1, max_length=200)
    entradas: int = Field(..., gt=0)
    total_pagado: float = Field(..., ge=0)
    estado: str = Field("confirmada", min_length=1, max_length=50)


class CompraRegistrada(BaseModel):
    usuario_id: UUID
    reserva_id: UUID
    registrada: bool


class UsuarioResponse(UsuarioBase):
    """Respuesta completa de usuario."""
    usuario_id: UUID
    creado_en: datetime
    actualizado_en: datetime
    historial_compras: List[HistorialCompra] = []

    class Config:
        from_attributes = True


class CompraAnonimizada(BaseModel):
    """Compra del historial sin ningun dato que identifique a la persona
    (se omite reserva_id y la fecha se generaliza al dia)."""
    evento_id: UUID
    evento_nombre: str
    fecha_compra: date
    entradas: int
    total_pagado: float
    estado: str


class UsuarioAnonimizado(BaseModel):
    """Usuario para analisis. Minimizacion de datos: no incluye nombre,
    apellido, email ni nro_documento (ni siquiera hasheados: son datos de
    baja entropia y un hash se revierte por diccionario). Solo queda lo que
    sirve para analizar: un pseudonimo para agrupar compras del mismo
    usuario, la categoria del documento, el mes de alta y el historial."""
    pseudonimo: str
    tipo_documento: TipoDocumento
    mes_alta: str
    historial_compras: List[CompraAnonimizada] = []