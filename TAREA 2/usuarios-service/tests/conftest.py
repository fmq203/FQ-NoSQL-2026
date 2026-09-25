import pytest
import pytest_asyncio
from httpx import AsyncClient
from src.main import create_app


@pytest.fixture(scope="session")
def app():
    """Crear app FastAPI para tests."""
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    """Cliente HTTP asíncrono para tests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def usuario_valido():
    """Datos de usuario válido para tests."""
    return {
        "tipo_documento": "DNI",
        "nro_documento": "12345678",
        "nombre": "Juan",
        "apellido": "Pérez",
        "email": "juan.perez@example.com"
    }


@pytest.fixture
def usuario_valido_2():
    """Segundo usuario válido para tests."""
    return {
        "tipo_documento": "Pasaporte",
        "nro_documento": "AB123456",
        "nombre": "María",
        "apellido": "González",
        "email": "maria.gonzalez@example.com"
    }