"""Historial de compras: POST /api/usuarios/{id}/historial (lo llama reservas-service)."""
import pytest
from httpx import AsyncClient
from uuid import uuid4


def _compra(**overrides):
    base = {
        "reserva_id": str(uuid4()),
        "evento_id": str(uuid4()),
        "evento_nombre": "Concierto Rock 2026",
        "entradas": 2,
        "total_pagado": 10000.0,
        "estado": "confirmada",
    }
    base.update(overrides)
    return base


@pytest.mark.integration
class TestHistorialCompras:
    @pytest.mark.asyncio
    async def test_compra_queda_en_el_historial_del_usuario(self, client: AsyncClient, usuario_valido):
        usuario_id = (await client.post("/api/usuarios", json=usuario_valido)).json()["usuario_id"]
        compra = _compra()

        response = await client.post(f"/api/usuarios/{usuario_id}/historial", json=compra)

        assert response.status_code == 201
        assert response.json()["registrada"] is True

        usuario = (await client.get(f"/api/usuarios/{usuario_id}")).json()
        assert len(usuario["historial_compras"]) == 1
        item = usuario["historial_compras"][0]
        assert item["reserva_id"] == compra["reserva_id"]
        assert item["evento_nombre"] == "Concierto Rock 2026"
        assert item["entradas"] == 2
        assert item["total_pagado"] == 10000.0

    @pytest.mark.asyncio
    async def test_reintento_con_misma_reserva_no_duplica(self, client: AsyncClient, usuario_valido):
        usuario_id = (await client.post("/api/usuarios", json=usuario_valido)).json()["usuario_id"]
        compra = _compra()

        primera = await client.post(f"/api/usuarios/{usuario_id}/historial", json=compra)
        segunda = await client.post(f"/api/usuarios/{usuario_id}/historial", json=compra)

        assert primera.status_code == 201
        assert segunda.status_code == 200
        assert segunda.json()["registrada"] is False
        usuario = (await client.get(f"/api/usuarios/{usuario_id}")).json()
        assert len(usuario["historial_compras"]) == 1

    @pytest.mark.asyncio
    async def test_reservas_distintas_se_acumulan(self, client: AsyncClient, usuario_valido):
        usuario_id = (await client.post("/api/usuarios", json=usuario_valido)).json()["usuario_id"]

        await client.post(f"/api/usuarios/{usuario_id}/historial", json=_compra())
        await client.post(f"/api/usuarios/{usuario_id}/historial", json=_compra())

        usuario = (await client.get(f"/api/usuarios/{usuario_id}")).json()
        assert len(usuario["historial_compras"]) == 2

    @pytest.mark.asyncio
    async def test_usuario_inexistente_es_404(self, client: AsyncClient):
        response = await client.post(f"/api/usuarios/{uuid4()}/historial", json=_compra())
        assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.parametrize("campo,valor", [("entradas", 0), ("total_pagado", -1), ("evento_nombre", "")])
    async def test_compra_invalida_es_422(self, client: AsyncClient, usuario_valido, campo, valor):
        usuario_id = (await client.post("/api/usuarios", json=usuario_valido)).json()["usuario_id"]
        response = await client.post(f"/api/usuarios/{usuario_id}/historial", json=_compra(**{campo: valor}))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_export_anonimizado_conserva_el_historial(self, client: AsyncClient, usuario_valido):
        """El enunciado pide que la anonimizacion mantenga el historial para analisis."""
        usuario_id = (await client.post("/api/usuarios", json=usuario_valido)).json()["usuario_id"]
        compra = _compra()
        await client.post(f"/api/usuarios/{usuario_id}/historial", json=compra)

        export = (await client.get("/api/usuarios/exportar")).json()

        assert len(export) == 1
        assert export[0]["email_hash"] != usuario_valido["email"]
        assert len(export[0]["historial_compras"]) == 1
        assert export[0]["historial_compras"][0]["evento_id"] == compra["evento_id"]
