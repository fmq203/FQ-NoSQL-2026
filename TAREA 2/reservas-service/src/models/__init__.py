"""
Modelos de dominio para Reservas Service.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class EstadoReserva(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    FALLIDA = "fallida"


class ReservaCreate(BaseModel):
    """Datos para crear una reserva."""
    usuario_id: UUID
    evento_id: UUID
    cantidad: int = Field(..., ge=1)
    categoria: str


class ReservaResponse(BaseModel):
    """Respuesta completa de reserva."""
    reserva_id: UUID
    usuario_id: UUID
    evento_id: UUID
    cantidad: int
    categoria: str
    estado: EstadoReserva
    total: float
    creado_en: datetime
    actualizado_en: datetime

    class Config:
        from_attributes = True


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResponse(BaseModel):
    status: str
    checks: dict
    service: str
    version: str
    timestamp: datetime