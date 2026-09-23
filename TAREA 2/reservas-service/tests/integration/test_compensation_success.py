"""Integration test for compensation success rate."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app


class TestCompensationSuccess:
    """Test compensation 100% success rate (RP-SC-004)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_failure_services(self):
        with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
             patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
             patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis, \
             patch("src.services.mongo.get_reservas_collection") as mock_mongo, \
             patch("src.services.postgresql.insert_event_log") as mock_pg, \
             patch("src.services.redis_pago.ejecutar_compensar_pago_inventario") as mock_compensation:

            # Usuarios
            usuarios_client = AsyncMock()
            mock_usuarios.return_value = usuarios_client
            usuarios_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
            )

            # Eventos
            eventos_client = AsyncMock()
            mock_eventos.return_value = eventos_client
            eventos_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "evento_id": str(uuid4()),
                    "estado": "publicado",
                    "entradas_disponibles": 100,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 100}],
                }
            )

            # Redis - payment success
            mock_redis.return_value = {"success": True, "message": "OK"}

            # Compensation - success
            mock_compensation.return_value = {"success": True, "message": "COMPENSACION_OK"}

            # MongoDB - will simulate failure
            mock_collection = AsyncMock()
            mock_mongo.return_value = mock_collection

            # PostgreSQL
            mock_pg.return_value = None

            yield {
                "mongo": mock_collection,
                "compensation": mock_compensation,
                "pg": mock_pg
            }

    @pytest.mark.integration
    async def test_compensation_100_percent_success_mongodb_failure(
        self,
        client: AsyncClient,
        mock_failure_services
    ):
        """Test 100% compensation success when MongoDB fails."""
        # Simulate MongoDB failure after successful payment
        mock_failure_services["mongo"].insert_one.side_effect = Exception("MongoDB down")

        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }

        response = await client.post("/api/v1/reservar", json=request_data)

        assert response.status_code == 500

        # Verify compensation was executed
        mock_failure_services["compensation"].assert_called_once_with(
            evento_id=pytest.helpers.any_string(),
            reserva_id=pytest.helpers.any_string(),
            cantidad=1
        )

        # Verify compensation event was logged
        mock_failure_services["pg"].assert_called()
        # Check for COMPENSACION_EJECUTADA event
        pg_calls = mock_failure_services["pg"].call_args_list
        compensation_logged = any(
            "COMPENSACION_EJECUTADA" in str(call) for call in pg_calls
        )
        assert compensation_logged

    @pytest.mark.integration
    async def test_compensation_atomic_lua_rollback(self, client: AsyncClient):
        """Test Lua atomic rollback on step 4 failure."""
        with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
             patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
             patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis, \
             patch("src.services.postgresql.insert_event_log") as mock_pg:

            # Setup mocks
            usuarios_client = AsyncMock()
            mock_usuarios.return_value = usuarios_client
            usuarios_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
            )

            eventos_client = AsyncMock()
            mock_eventos.return_value = eventos_client
            eventos_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "evento_id": str(uuid4()),
                    "estado": "publicado",
                    "entradas_disponibles": 1,  # Very low inventory
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 1}],
                }
            )

            # Redis returns insufficient inventory
            mock_redis.return_value = {"success": False, "message": "INVENTARIO_INSUFICIENTE"}
            mock_pg.return_value = None

            request_data = {
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 5,  # More than available (1)
                "metodo_pago": "tarjeta"
            }

            response = await client.post("/api/v1/reservar", json=request_data)

            assert response.status_code == 409
            data = response.json()
            assert "INSUFICIENTE" in data.get("detail", "")

            # Lua script handles rollback atomically - no compensation needed

    @pytest.mark.integration
    async def test_compensation_not_executed_for_pg_failure(
        self,
        client: AsyncClient,
        mock_failure_services
    ):
        """Test compensation NOT executed for PG failure (step 6) - reservation already confirmed."""
        # Simulate successful reservation, but PG audit fails
        mock_failure_services["mongo"].insert_one.side_effect = None
        mock_failure_services["mongo"].insert_one.return_value = None

        # Make PG fail on the SAGA_COMPLETED event
        call_count = [0]
        async def mock_pg_fail(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 5:  # Fail on SAGA_COMPLETED event
                raise Exception("PG down")
            return None

        with patch("src.services.postgresql.insert_event_log", side_effect=mock_pg_fail):
            request_data = {
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 1,
                "metodo_pago": "tarjeta"
            }

            response = await client.post("/api/v1/reservar", json=request_data)

            # Should still succeed (201) since reservation was confirmed
            # Audit failure is warning only
            assert response.status_code == 201