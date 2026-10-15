import csv
import io
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.config import get_settings


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


@pytest.mark.contract
class TestExportUsuarios:
    """Contract tests para GET /api/usuarios/exportar."""

    @pytest.mark.asyncio
    async def test_exportar_json(self, client: AsyncClient, usuario_valido):
        """GET /api/usuarios/exportar?format=json -> 200 con usuarios anonimizados."""
        await client.post("/api/usuarios", json=usuario_valido)

        response = await client.get("/api/usuarios/exportar?format=json")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert set(data[0]) == {"pseudonimo", "tipo_documento", "mes_alta", "historial_compras"}

    @pytest.mark.asyncio
    async def test_exportar_no_contiene_ningun_dato_personal(self, client: AsyncClient, usuario_valido):
        """Anonimizacion por minimizacion: ni el dato real ni un hash de el."""
        creado = (await client.post("/api/usuarios", json=usuario_valido)).json()
        await client.post(f"/api/usuarios/{creado['usuario_id']}/historial", json=_compra())

        for formato in ("json", "csv"):
            texto = (await client.get(f"/api/usuarios/exportar?format={formato}")).text.lower()
            for dato in (
                usuario_valido["nombre"], usuario_valido["apellido"],
                usuario_valido["email"], usuario_valido["nro_documento"],
                creado["usuario_id"],
            ):
                assert dato.lower() not in texto, f"{dato!r} aparece en el export {formato}"

    @pytest.mark.asyncio
    async def test_exportar_formato_invalido(self, client: AsyncClient):
        """GET /api/usuarios/exportar?format=xml -> 400 Bad Request."""
        response = await client.get("/api/usuarios/exportar?format=xml")

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == 400

    @pytest.mark.asyncio
    async def test_exportar_conserva_el_historial_sin_reserva_id(self, client: AsyncClient, usuario_valido):
        creado = (await client.post("/api/usuarios", json=usuario_valido)).json()
        compra = _compra()
        await client.post(f"/api/usuarios/{creado['usuario_id']}/historial", json=compra)

        export = (await client.get("/api/usuarios/exportar")).json()

        historial = export[0]["historial_compras"]
        assert len(historial) == 1
        assert historial[0]["evento_id"] == compra["evento_id"]
        assert historial[0]["evento_nombre"] == "Concierto Rock 2026"
        assert historial[0]["entradas"] == 2
        assert historial[0]["total_pagado"] == 10000.0
        assert "reserva_id" not in historial[0]
        assert len(historial[0]["fecha_compra"]) == 10  # YYYY-MM-DD: generalizada al dia

    @pytest.mark.asyncio
    async def test_pseudonimo_es_consistente_dentro_del_export_y_distinto_entre_usuarios(
        self, client: AsyncClient, usuario_valido
    ):
        otro = {**usuario_valido, "nro_documento": "99999999", "email": "otro@example.com"}
        await client.post("/api/usuarios", json=usuario_valido)
        await client.post("/api/usuarios", json=otro)

        a = (await client.get("/api/usuarios/exportar")).json()
        b = (await client.get("/api/usuarios/exportar")).json()

        assert len({u["pseudonimo"] for u in a}) == 2
        assert {u["pseudonimo"] for u in a} == {u["pseudonimo"] for u in b}

    @pytest.mark.asyncio
    async def test_la_clave_configurada_cambia_los_pseudonimos(self, client: AsyncClient, usuario_valido):
        await client.post("/api/usuarios", json=usuario_valido)
        settings = get_settings()
        original = settings.export_pseudonym_key
        try:
            settings.export_pseudonym_key = "clave-A"
            con_a = (await client.get("/api/usuarios/exportar")).json()[0]["pseudonimo"]
            con_a_otra_vez = (await client.get("/api/usuarios/exportar")).json()[0]["pseudonimo"]
            settings.export_pseudonym_key = "clave-B"
            con_b = (await client.get("/api/usuarios/exportar")).json()[0]["pseudonimo"]
        finally:
            settings.export_pseudonym_key = original

        assert con_a == con_a_otra_vez  # clave fija -> pseudonimo estable (pseudonimizacion)
        assert con_a != con_b

    @pytest.mark.asyncio
    async def test_exportar_csv(self, client: AsyncClient, usuario_valido):
        creado = (await client.post("/api/usuarios", json=usuario_valido)).json()
        await client.post(f"/api/usuarios/{creado['usuario_id']}/historial", json=_compra(evento_nombre="=HYPERLINK(1)"))
        sin_compras = {**usuario_valido, "nro_documento": "88888888", "email": "sin.compras@example.com"}
        await client.post("/api/usuarios", json=sin_compras)

        response = await client.get("/api/usuarios/exportar?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        filas = list(csv.DictReader(io.StringIO(response.text)))
        assert len(filas) == 2  # 1 compra + 1 usuario sin compras
        con_compra = next(f for f in filas if f["evento_id"])
        assert con_compra["entradas"] == "2"
        assert con_compra["evento_nombre"] == "'=HYPERLINK(1)"  # neutraliza formula injection
        vacia = next(f for f in filas if not f["evento_id"])
        assert vacia["pseudonimo"] and vacia["entradas"] == ""
