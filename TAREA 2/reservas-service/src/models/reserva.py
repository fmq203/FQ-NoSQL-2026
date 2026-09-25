"""Pydantic models for Reservas Service."""
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator
from dataclasses import dataclass, field

from .enums import MetodoPago, EstadoReserva


class ReservaCreateRequest(BaseModel):
    """Request para crear una reserva."""
    usuario_id: UUID
    evento_id: UUID
    cantidad: int = Field(..., gt=0, description="Cantidad de entradas (>0)")
    categoria: str = Field(..., min_length=1, description="Categoria de precio del evento (debe existir en evento.precios[])")
    metodo_pago: MetodoPago
    reserva_id: Optional[UUID] = Field(default_factory=uuid4, description="Idempotency key (UUID v4). If provided, used for idempotency check.")

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Cantidad debe ser mayor a 0")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
                "evento_id": "550e8400-e29b-41d4-a716-446655440001",
                "cantidad": 2,
                "categoria": "general",
                "metodo_pago": "tarjeta",
            }
        }
    }


class ReservaResponse(BaseModel):
    """Response de reserva exitosa."""
    reserva_id: str
    estado: str
    numero_confirmacion: str


class RFC7807Error(BaseModel):
    """Formato de error estandar (RFC 7807) usado por todos los servicios de EventFlow."""
    type: str = Field(..., example="https://eventflow.example.com/errors/not-found")
    title: str = Field(..., example="Not Found")
    status: int = Field(..., example=404)
    detail: str = Field(..., example="Usuario no encontrado")
    instance: str = Field(..., example="/api/reservar")
    correlation_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")


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
    categoria: str
    reserva_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    evento_data: Optional[Dict] = None
    usuario_data: Optional[Dict] = None
    categoria_disponibles: Optional[int] = None
    precio_unitario: Optional[float] = None
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