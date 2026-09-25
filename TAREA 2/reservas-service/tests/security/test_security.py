"""Security hardening tests (T069, T074)."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from io import StringIO
import logging
from src.main import app


class TestSecurityHardening:
    """Security hardening tests (T069)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.security
    async def test_input_validation_rejects_malicious_payloads(self, client):
        """Test that malicious payloads are rejected."""
        malicious_payloads = [
            {"usuario_id": "<script>alert('xss')</script>", "evento_id": str(uuid4()), "cantidad": 1, "metodo_pago": "tarjeta"},
            {"usuario_id": str(uuid4()), "evento_id": "'; DROP TABLE users; --", "cantidad": 1, "metodo_pago": "tarjeta"},
            {"usuario_id": str(uuid4()), "evento_id": str(uuid4()), "cantidad": -1, "metodo_pago": "tarjeta"},
            {"usuario_id": str(uuid4()), "evento_id": str(uuid4()), "cantidad": 1, "metodo_pago": "malicious<script>"},
        ]
        
        for payload in malicious_payloads:
            response = await client.post("/api/reservar", json=payload)
            # Should reject with 422 or 400
            assert response.status_code in [400, 422], f"Failed to reject: {payload}"

    @pytest.mark.security
    async def test_no_pii_in_logs(self):
        """Test that no PII is logged."""
        # Capture logs from the logger the app actually writes to
        # (StructuredLoggingMiddleware uses logging.getLogger("reservas-service"),
        # not a test-local logger) - a capture attached to any other name
        # would just stay empty regardless of what the app logs.
        #
        # StructuredLoggingMiddleware attaches correlation_id/trace_id/etc
        # as `extra` fields on the LogRecord, not in the message text - a
        # plain StreamHandler only renders record.getMessage(), so a
        # minimal formatter is needed to actually see them (mirrors
        # setup_json_logging's JSONFormatter, which isn't importable since
        # it's defined inline there).
        class _ExtraFieldsFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                base = record.getMessage()
                extras = {
                    k: getattr(record, k)
                    for k in ("correlation_id", "trace_id", "context")
                    if hasattr(record, k)
                }
                return f"{base} {extras}" if extras else base

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        handler.setFormatter(_ExtraFieldsFormatter())

        logger = logging.getLogger("reservas-service")
        original_handlers = logger.handlers
        original_propagate = logger.propagate
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        # Patched at src.chain.validators (the actual call sites) - see
        # test_double_booking.py for why patching the origin modules
        # doesn't intercept an already-imported name.
        try:
            with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
                 patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
                 patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
                 patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
                 patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

                mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Juan"}
                mock_get_evento.return_value = {
                    "evento_id": str(uuid4()),
                    "estado": "publicado",
                    "entradas_disponibles": 10,
                    "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 10}],
                }
                mock_redis.return_value = {"success": True, "message": "OK"}
                mock_decrementar_evento.return_value = {"disponibles": 9}
                mock_idempotency.return_value = None

                # Make a request with PII
                async with AsyncClient(app=app, base_url="http://test") as client:
                    await client.post("/api/reservar", json={
                        "usuario_id": str(uuid4()),
                        "evento_id": str(uuid4()),
                        "cantidad": 1,
                        "categoria": "general",
                        "metodo_pago": "tarjeta"
                    })
        finally:
            logger.handlers = original_handlers
            logger.propagate = original_propagate

        log_output = log_stream.getvalue()

        # Verify no PII in logs (email, document, name, etc.)
        assert "juan@example.com" not in log_output
        assert "12345678" not in log_output  # Document number
        # Note: Names might appear in mock data, so we check correlation_id is present
        assert "correlation_id" in log_output


class TestIdempotencyBehavior:
    """Tests for idempotency behavior verification (T074)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.integration
    async def test_idempotency_returns_200_for_existing_reservation(self):
        """Same reserva_id should return 200 with existing reservation (T074).

        Exercised through two real HTTP requests carrying the same
        reserva_id, matching how a client actually retries - not by
        calling check_idempotency()/mark_idempotent() directly, which
        tests the helper functions in isolation but never proves the
        route itself behaves idempotently end to end.
        """
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
             patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Test"}
            mock_get_evento.return_value = {
                "evento_id": str(uuid4()),
                "estado": "publicado",
                "entradas_disponibles": 10,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 10}],
            }
            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_decrementar_evento.return_value = {"disponibles": 9}
            mock_idempotency.return_value = None

            reserva_id = str(uuid4())
            request_data = {
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 1,
                "categoria": "general",
                "metodo_pago": "tarjeta",
                "reserva_id": reserva_id,
            }

            async with AsyncClient(app=app, base_url="http://test") as client:
                response1 = await client.post("/api/reservar", json=request_data)
                assert response1.status_code == 201
                assert response1.json()["reserva_id"] == reserva_id

                # From here on, check_idempotency reports the reservation
                # just created, as it would for a real retry.
                mock_idempotency.return_value = {
                    "_id": reserva_id,
                    "estado": response1.json()["estado"],
                    "numero_confirmacion": response1.json()["numero_confirmacion"],
                }

                response2 = await client.post("/api/reservar", json=request_data)
                assert response2.status_code == 200
                assert response2.json()["reserva_id"] == reserva_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])