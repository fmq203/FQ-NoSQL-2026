"""Idempotency helper for Reservas Service."""
from typing import Optional
from uuid import UUID
from datetime import datetime
import os


async def check_idempotency(reserva_id: UUID) -> Optional[dict]:
    """
    Verifica si ya existe una reserva con el mismo reserva_id.
    
    Returns:
        Reserva existente si existe, None si no existe.
    """
    from src.services.mongo import get_reservas_collection
    from src.services.redis_pago import obtener_pago
    from src.services.postgresql import get_events_by_aggregate
    
    # Check MongoDB
    collection = await get_reservas_collection()
    existing = await collection.find_one({"_id": reserva_id})
    if existing:
        return existing
    
    # Check Redis
    pago = await obtener_pago(str(reserva_id))
    if pago:
        return {"source": "redis", "data": pago}
    
    # Check PostgreSQL
    events = await get_events_by_aggregate(reserva_id)
    if events:
        return {"source": "postgresql", "events": events}
    
    return None


def generate_confirmation_number(reserva_id: UUID) -> str:
    """
    Genera número de confirmación: CONF-YYYYMMDD-XXXXXXXX
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    short_uuid = str(reserva_id).replace("-", "")[:8].upper()
    return f"CONF-{date_str}-{short_uuid}"


async def mark_idempotent(reserva_id: UUID, source: str = "mongodb") -> bool:
    """
    Marca reserva_id como procesado para idempotencia.
    """
    # En este caso, la inserción en MongoDB con _id único ya garantiza idempotencia
    # Esta función es placeholder para lógica adicional si se necesita
    return True