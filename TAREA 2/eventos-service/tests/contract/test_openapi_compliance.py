"""Contract tests for OpenAPI 3.1 spec compliance using schemathesis."""

import pytest
import schemathesis
from motor.motor_asyncio import AsyncIOMotorClient

import src.services.mongodb as mongodb_module
from src.config import get_settings
from src.main import create_app

# schemathesis construye el schema (y hace las llamadas ASGI de
# schema.parametrize()) de forma sincrona contra una app fija, a
# diferencia del resto de la suite que crea un `app` nuevo por test
# (fixture async_client/app en conftest.py) para aislar cada test con su
# propia base de datos. Esta app es solo para fuzzing de contrato, no
# para aserciones de negocio, asi que una DB de test dedicada alcanza -
# no hace falta el aislamiento por-test de conftest.py.
_settings = get_settings()
_settings.mongodb_database = "eventflow_schemathesis_test"
_settings.mongodb_collection = "eventos"

# Limpiar entre sesiones de pytest: sin esto, los nombres simples que
# Hypothesis favorece para shrinking (ej. "0", "") persisten de una
# corrida a la siguiente y disparan el 409 real de "nombre duplicado"
# (evento_service.py) en una request que schemathesis esperaba que
# devolviera 201, dando falsos negativos. Usa un cliente descartable
# propio (no mongodb_module._client) para no atar ese cliente a un event
# loop que pytest-asyncio va a cerrar apenas termine este drop.
import asyncio as _asyncio


async def _drop_schemathesis_test_db() -> None:
    client = AsyncIOMotorClient(_settings.mongodb_uri, uuidRepresentation="standard")
    try:
        await client.drop_database(_settings.mongodb_database)
    finally:
        client.close()


_asyncio.run(_drop_schemathesis_test_db())

mongodb_module._client = AsyncIOMotorClient(_settings.mongodb_uri, uuidRepresentation="standard")
mongodb_module._database = mongodb_module._client[_settings.mongodb_database]

app = create_app()
# FastAPI/Pydantic v2 generan OpenAPI 3.1.0; el soporte de schemathesis
# 3.x para 3.1 es parcial y lo rechaza por default. Forzamos que lo
# parsee como 3.0 (compatible en la practica para las validaciones de
# forma/tipos que generamos aca).
schema = schemathesis.openapi.from_asgi("/openapi.json", app, force_schema_version="30")


@pytest.mark.contract
class TestOpenAPICompliance:
    """Tests that API implementation matches OpenAPI 3.1 specification."""

    @pytest.mark.asyncio
    async def test_post_eventos_compliance(self, async_client):
        """Test POST /api/eventos matches OpenAPI spec."""
        valid_event = {
            "nombre": "Test Event",
            "estado": "publicado",
            "aforo_total": 100,
            "entradas_disponibles": 100,
            "precios": [
                {"categoria": "VIP", "precio": 15000.00, "disponibles": 10},
                {"categoria": "General", "precio": 5000.00, "disponibles": 90},
            ],
            "ubicacion": {
                "ciudad": "Buenos Aires",
                "pais": "Argentina",
                "direccion": "Estadio Test",
            },
        }

        response = await async_client.post("/api/eventos", json=valid_event)

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_get_eventos_compliance(self, async_client):
        """Test GET /api/eventos/{id} matches OpenAPI spec."""
        valid_event = {
            "nombre": "Test Event Get",
            "estado": "publicado",
            "aforo_total": 100,
            "entradas_disponibles": 100,
            "precios": [{"categoria": "General", "precio": 5000.00, "disponibles": 100}],
            "ubicacion": {"ciudad": "Buenos Aires", "pais": "Argentina"},
        }
        create_response = await async_client.post("/api/eventos", json=valid_event)
        event_id = create_response.json()["evento_id"]

        response = await async_client.get(f"/api/eventos/{event_id}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_check_compliance(self, async_client):
        """Test GET /health matches OpenAPI spec."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "checks" in data
        assert "mongodb" in data["checks"]
        assert data["checks"]["mongodb"] in ["ok", "slow", "down"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_compliance(self, async_client):
        """Test GET /metrics matches OpenAPI spec."""
        response = await async_client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        assert "http_requests_total" in response.text or "http_request_duration_seconds" in response.text


# Casos generados por schemathesis a partir del spec OpenAPI 3.1: fuzzing
# property-based que valida que toda respuesta cumple el schema (status
# codes documentados, forma de la respuesta, etc.) para cada
# operacion. A diferencia de la version anterior de este archivo, no
# silencia excepciones con pytest.skip - una violacion real del contrato
# debe fallar el test.
@schema.parametrize()
def test_openapi_spec_case(case):
    response = case.call()
    case.validate_response(response)
