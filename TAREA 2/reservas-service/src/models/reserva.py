"""Pydantic models for Reservas Service."""
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from dataclasses import dataclass, field

from .enums import MetodoPago, EstadoReserva


class ReservaRequest(BaseModel):
    """Request para crear una reserva."""
    usuario_id: UUID
    evento_id: UUID
    cantidad: int = Field(..., gt=0, description="Cantidad de entradas (>0)")
    metodo_pago: MetodoPago
    
    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Cantidad debe ser mayor a 0")
        return v


class ReservaResponse(BaseModel):
    """Response de reserva exitosa."""
    reserva_id: str
    estado: str
    numero_confirmacion: str


class ReservaDB(BaseModel):
    """Modelo de reserva en MongoDB."""
    _id: UUID
    usuario_id: UUID
    evento_id: UUID
    cantidad: int
    metodo_pago: str
    monto_total: float
    numero_confirmacion: str
    estado: str
    creado_en: datetime
    saga_log: List[Dict[str, Any]] = Field(default_factory=list)


@dataclass
class ReservaContext:
    """Context que viaja por la Chain of Responsibility."""
    usuario_id: UUID
    evento_id: UUID
    cantidad: int
    metodo_pago: str
    reserva_id: UUID = field(default_factory=UUID)
    correlation_id: UUID = field(default_factory=UUID)
    evento_data: Optional[Dict] = None
    usuario_data: Optional[Dict] = None
    pago_data: Optional[Dict] = None
    reserva_data: Optional[Dict] = None
    error: Optional[str] = None
    status_code: int = 200
    saga_log: List[Dict] = field(default_factory=list)
    compensation_triggered: bool = False


class SagaStep(str, Enum):
    """Pasos de la SAGA."""
    VALIDAR_DATOS = "VALIDAR_DATOS"
    VALIDAR_USUARIO = "VALIDAR_USUARIO"
    VALIDAR_EVENTO = "VALIDAR_EVENTO"
    PROCESAR_PAGO = "PROCESAR_PAGO"
    CONFIRMAR_RESERVA = "CONFIRMAR_RESERVA"
    AUDITAR = "AUDITAR"


class EventType(str, Enum):
    """Tipos de eventos para Event Sourcing."""
    SAGA_STARTED = "SAGA_STARTED"
    USUARIO_VALIDADO = "USUARIO_VALIDADO"
    EVENTO_VALIDADO = "EVENTO_VALIDADO"
    PAGO_PROCESADO = "PAGO_PROCESADO"
    INVENTARIO_DECREMENTADO = "INVENTARIO_DECREMENTADO"
    RESERVA_CONFIRMADA = "RESERVA_CONFIRMADA"
    SAGA_COMPLETED = "SAGA_COMPLETED"
    SAGA_FAILED = "SAGA_FAILED"
    COMPENSACION_EJECUTADA = "COMPENSACION_EJECUTADA"