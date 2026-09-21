"""Enums for Reservas Service."""
from enum import Enum


class MetodoPago(str, Enum):
    TARJETA = "tarjeta"
    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"
    MERCADOPAGO = "mercadopago"


class EstadoReserva(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    FALLIDA = "fallida"