"""Cache AP de lecturas: GET /api/eventos/{id} (ver services/lectura_cache.py)."""
from uuid import uuid4

from src.services.evento_service import EventoService

import pytest
from unittest.mock import patch
from pymongo.errors import ServerSelectionTimeoutError

from src.config import get_settings
import src.services.lectura_cache as lectura_cache

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _falla(peticion) -> bool:
    """True si la request termina en error 5xx (el cliente de test re-lanza
    la excepcion de la app en vez de devolver la respuesta 500)."""
    try:
        return (await peticion).status_code >= 500
    except ServerSelectionTimeoutError:
        return True


class _RedisCaido:
    async def get(self, *a, **k):
        raise ConnectionError("redis caido")

    set = delete = get


def _espiar():
    return patch.object(EventoService, "get_event", autospec=True, side_effect=EventoService.get_event)


async def test_segunda_lectura_sale_del_cache_sin_tocar_mongo(async_client, created_event_id):
    with _espiar() as spy:
        r1 = await async_client.get(f"/api/eventos/{created_event_id}")
        r2 = await async_client.get(f"/api/eventos/{created_event_id}")

    assert (r1.headers["X-Cache"], r2.headers["X-Cache"]) == ("MISS", "HIT")
    assert r1.json() == r2.json()
    assert spy.call_count == 1


async def test_cache_control_no_cache_fuerza_lectura_fresca(async_client, created_event_id):
    with _espiar() as spy:
        await async_client.get(f"/api/eventos/{created_event_id}")
        r = await async_client.get(f"/api/eventos/{created_event_id}", headers={"Cache-Control": "no-cache"})

    assert r.headers["X-Cache"] == "BYPASS"
    assert spy.call_count == 2


async def test_cambiar_el_inventario_invalida_el_cache(async_client, created_event_id):
    antes = await async_client.get(f"/api/eventos/{created_event_id}")
    assert antes.json()["precios"][0]["disponibles"] == 100

    r = await async_client.post(
        f"/api/eventos/{created_event_id}/decrementar-inventario",
        json={"categoria": "General", "cantidad": 10},
    )
    assert r.status_code == 200

    despues = await async_client.get(f"/api/eventos/{created_event_id}")
    assert despues.headers["X-Cache"] == "MISS"
    assert despues.json()["precios"][0]["disponibles"] == 90


async def test_con_mongo_caido_se_sirve_la_entrada_vencida(async_client, created_event_id):
    """AP: se prefiere un dato posiblemente desactualizado a no responder."""
    tibio = await async_client.get(f"/api/eventos/{created_event_id}")
    settings = get_settings()
    original = settings.cache_fresh_seconds
    settings.cache_fresh_seconds = 0  # la entrada pasa a "vencida pero utilizable"
    try:
        with patch.object(EventoService, "get_event", side_effect=ServerSelectionTimeoutError("mongo caido")):
            r = await async_client.get(f"/api/eventos/{created_event_id}")
            estricta_fallo = await _falla(
                async_client.get(f"/api/eventos/{created_event_id}", headers={"Cache-Control": "no-cache"})
            )
    finally:
        settings.cache_fresh_seconds = original

    assert r.status_code == 200
    assert r.headers["X-Cache"] == "STALE"
    assert r.json() == tibio.json()
    assert estricta_fallo  # el camino transaccional nunca recibe datos vencidos


async def test_un_404_no_se_cachea(async_client):
    inexistente = uuid4()
    with _espiar() as spy:
        r1 = await async_client.get(f"/api/eventos/{inexistente}")
        r2 = await async_client.get(f"/api/eventos/{inexistente}")

    assert (r1.status_code, r2.status_code) == (404, 404)
    assert spy.call_count == 2


async def test_si_redis_cae_las_lecturas_siguen_yendo_a_mongo(async_client, created_event_id):
    lectura_cache._redis = _RedisCaido()

    r1 = await async_client.get(f"/api/eventos/{created_event_id}")
    r2 = await async_client.get(f"/api/eventos/{created_event_id}")

    assert (r1.status_code, r2.status_code) == (200, 200)
    assert (r1.headers["X-Cache"], r2.headers["X-Cache"]) == ("MISS", "MISS")
