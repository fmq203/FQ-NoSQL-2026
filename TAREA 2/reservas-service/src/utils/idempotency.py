"""Idempotency helper for Reservas Service."""
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)


async def check_idempotency(reserva_id: UUID) -> Optional[dict]:
    """
    Verifica si ya existe una reserva con el mismo reserva_id.

    Cada backend se consulta de forma best-effort: si Redis o PostgreSQL
    no estan disponibles, no debe impedir que la reserva se procese (son
    chequeos secundarios para detectar reintentos a mitad de camino). La
    fuente de verdad primaria es MongoDB (_id = reserva_id, unico por
    diseno) y si esa consulta falla, sí se propaga - sin Mongo la SAGA no
    puede continuar de todas formas.

    Returns:
        Reserva existente si existe, None si no existe.
    """
    from ..services.mongo import get_reservas_collection
    from ..services.redis_pago import obtener_pago
    from ..services.postgresql import get_events_by_aggregate
    from ..services.metrics import record_idempotency_hit

    # Check MongoDB (fuente de verdad - si esto falla, se propaga)
    collection = await get_reservas_collection()
    existing = await collection.find_one({"_id": reserva_id})
    if existing:
        record_idempotency_hit()
        return existing

    # Check Redis (best-effort)
    try:
        pago = await obtener_pago(str(reserva_id))
        if pago:
            record_idempotency_hit()
            return {"source": "redis", "data": pago}
    except Exception as e:
        logger.warning(f"No se pudo verificar idempotencia en Redis: {e}")

    # Check PostgreSQL (best-effort)
    try:
        events = await get_events_by_aggregate(reserva_id)
        if events:
            record_idempotency_hit()
            return {"source": "postgresql", "events": events}
    except Exception as e:
        logger.warning(f"No se pudo verificar idempotencia en PostgreSQL: {e}")

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
