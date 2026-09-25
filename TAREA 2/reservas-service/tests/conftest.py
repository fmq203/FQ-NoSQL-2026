import pytest
import pytest_asyncio
from httpx import AsyncClient
from src.main import create_app


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def reserva_valida():
    return {
        "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
        "evento_id": "550e8400-e29b-41d4-a716-446655440001",
        "cantidad": 2,
        "categoria": "General"
    }