from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from enum import Enum


class EstadoEvento(str, Enum):
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    CANCELADO = "cancelado"
    FINALIZADO = "finalizado"


class PrecioCategoria(BaseModel):
    categoria: str = Field(..., min_length=1, max_length=100)
    precio: Decimal = Field(..., ge=0, decimal_places=2)
    disponibles: int = Field(..., ge=0)

    @field_validator('precio')
    @classmethod
    def validate_precio_precision(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError('precio must have at most 2 decimal places')
        return v


class Ubicacion(BaseModel):
    ciudad: str = Field(..., min_length=1, max_length=100)
    pais: str = Field(..., min_length=1, max_length=100)
    direccion: Optional[str] = Field(None, max_length=500)


class EventoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    estado: EstadoEvento
    aforo_total: int = Field(..., ge=0)
    entradas_disponibles: int = Field(..., ge=0)
    precios: List[PrecioCategoria] = Field(..., min_length=1)
    ubicacion: Ubicacion

    @model_validator(mode='after')
    def validate_aforo_y_entradas(self) -> 'EventoCreate':
        if self.entradas_disponibles > self.aforo_total:
            raise ValueError('entradas_disponibles cannot exceed aforo_total')
        return self

    @model_validator(mode='after')
    def validate_precios_categorias_unicas(self) -> 'EventoCreate':
        categorias = [p.categoria for p in self.precios]
        if len(categorias) != len(set(categorias)):
            raise ValueError('categoria must be unique within precios')
        return self

    @model_validator(mode='after')
    def validate_precios_disponibles_sum(self) -> 'EventoCreate':
        total_disponibles = sum(p.disponibles for p in self.precios)
        if total_disponibles > self.entradas_disponibles:
            raise ValueError('sum of precios.disponibles cannot exceed entradas_disponibles')
        return self


class EventoResponse(EventoCreate):
    evento_id: UUID
    creado_en: datetime
    actualizado_en: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
        use_enum_values = True


class EventoInDB(EventoResponse):
    """Internal model matching MongoDB document"""
    id: UUID = Field(alias='evento_id', serialization_alias='_id')

    class Config:
        populate_by_name = True
        use_enum_values = True


class AjusteInventarioRequest(BaseModel):
    """Body para decrementar/incrementar el inventario de una categoria.

    Uso interno: llamado por reservas-service tras confirmar (decrementar) o
    compensar (incrementar) un paso de la SAGA, para que entradas_disponibles
    y precios[].disponibles reflejen las ventas reales en vez de quedar
    congelados en el valor de creacion del evento.
    """
    categoria: str = Field(..., min_length=1)
    cantidad: int = Field(..., gt=0)


class AjusteInventarioResponse(BaseModel):
    evento_id: UUID
    categoria: str
    disponibles: int
    entradas_disponibles: int


class RFC7807Error(BaseModel):
    """Formato de error estandar (RFC 7807) usado por todos los servicios de EventFlow."""
    type: str = Field(..., example="https://eventflow.example.com/errors/not-found")
    title: str = Field(..., example="Not Found")
    status: int = Field(..., example=404)
    detail: str = Field(..., example="Evento no encontrado")
    instance: str = Field(..., example="/api/eventos")
    correlation_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")