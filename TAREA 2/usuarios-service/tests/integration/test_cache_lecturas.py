"""Cache AP de lecturas: GET /api/usuarios/{id} (ver services/lectura_cache.py)."""
from uuid import uuid4

from src.services.usuario_service import UsuarioService

import pytest
from unittest.mock import patch
from pymongo.errors import ServerSelectionTimeoutError

from src.config import get_settings
import src.services.lectura_cache as lectura_cache

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _RedisCaido:
    async def get(self, *a, **k):
        raise ConnectionError("redis caido")

    set = delete = get


def _espiar():
    return patch.object(UsuarioService, "obtener_usuario", autospec=True, side_effect=UsuarioService.obtener_usuario)


async def _crear(client, usuario_valido):
    return (await client.post("/api/usuarios", json=usuario_valido)).json()["usuario_id"]


async def test_segunda_lectura_sale_del_cache_sin_tocar_mongo(client, usuario_valido):
    usuario_id = await _crear(client, usuario_valido)
    with _espiar() as spy:
        r1 = await client.get(f"/api/usuarios/{usuario_id}")
        r2 = await client.get(f"/api/usuarios/{usuario_id}")

    assert (r1.headers["X-Cache"], r2.headers["X-Cache"]) == ("MISS", "HIT")
    assert r1.json() == r2.json()
    assert spy.call_count == 1


async def test_cache_control_no_cache_fuerza_lectura_fresca(client, usuario_valido):
    usuario_id = await _crear(client, usuario_valido)
    await client.get(f"/api/usuarios/{usuario_id}")

    r = await client.get(f"/api/usuarios/{usuario_id}", headers={"Cache-Control": "no-cache"})

    assert r.headers["X-Cache"] == "BYPASS"


async def test_registrar_una_compra_invalida_el_cache(client, usuario_valido):
    usuario_id = await _crear(client, usuario_valido)
    assert (await client.get(f"/api/usuarios/{usuario_id}")).json()["historial_compras"] == []

    await client.post(
        f"/api/usuarios/{usuario_id}/historial",
        json={"reserva_id": str(uuid4()), "evento_id": str(uuid4()), "evento_nombre": "Rock",
              "entradas": 1, "total_pagado": 100.0},
    )

    despues = await client.get(f"/api/usuarios/{usuario_id}")
    assert despues.headers["X-Cache"] == "MISS"
    assert len(despues.json()["historial_compras"]) == 1


async def test_con_mongo_caido_se_sirve_la_entrada_vencida(client, usuario_valido):
    usuario_id = await _crear(client, usuario_valido)
    tibio = await client.get(f"/api/usuarios/{usuario_id}")
    settings = get_settings()
    original = settings.cache_fresh_seconds
    settings.cache_fresh_seconds = 0
    try:
        with patch.object(UsuarioService, "obtener_usuario", side_effect=ServerSelectionTimeoutError("mongo caido")):
            r = await client.get(f"/api/usuarios/{usuario_id}")
            estricta = await client.get(f"/api/usuarios/{usuario_id}", headers={"Cache-Control": "no-cache"})
    finally:
        settings.cache_fresh_seconds = original

    assert r.status_code == 200
    assert r.headers["X-Cache"] == "STALE"
    assert r.json() == tibio.json()
    # el camino transaccional nunca recibe datos vencidos: Mongo caido -> 503, no 500
    assert estricta.status_code == 503
    assert estricta.headers["Retry-After"] == "5"
    assert estricta.json()["type"].endswith("/service-unavailable")


async def test_un_404_no_se_cachea(client):
    inexistente = uuid4()
    with _espiar() as spy:
        r1 = await client.get(f"/api/usuarios/{inexistente}")
        r2 = await client.get(f"/api/usuarios/{inexistente}")

    assert (r1.status_code, r2.status_code) == (404, 404)
    assert spy.call_count == 2


async def test_si_redis_cae_las_lecturas_siguen_yendo_a_mongo(client, usuario_valido):
    usuario_id = await _crear(client, usuario_valido)
    lectura_cache._redis = _RedisCaido()

    r1 = await client.get(f"/api/usuarios/{usuario_id}")
    r2 = await client.get(f"/api/usuarios/{usuario_id}")

    assert (r1.status_code, r2.status_code) == (200, 200)
    assert (r1.headers["X-Cache"], r2.headers["X-Cache"]) == ("MISS", "MISS")
