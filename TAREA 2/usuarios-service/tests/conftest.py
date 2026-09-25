import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from src.config import get_settings
from src.main import create_app


@pytest.fixture(scope="session")
def test_mongodb_uri():
    """Get test MongoDB URI from environment or use default."""
    return os.getenv("TEST_MONGODB_URI", "mongodb://localhost:27017")


@pytest_asyncio.fixture(scope="function")
async def test_db(test_mongodb_uri):
    """Create an isolated test database and clean up after."""
    client = AsyncIOMotorClient(test_mongodb_uri, uuidRepresentation="standard")
    db_name = "eventflow_test"
    db = client[db_name]

    await client.drop_database(db_name)

    yield db

    await client.drop_database(db_name)
    client.close()


@pytest_asyncio.fixture
async def app(test_db):
    """Create app FastAPI para tests.

    httpx.AsyncClient(app=app) never fires FastAPI's lifespan (its
    ASGITransport has no lifespan handling at all), so
    connect_to_mongodb() never runs and src.services.mongodb's module-
    global _client/_database stay None for the whole test - every
    request then fails with "MongoDB no inicializado". Injecting an
    already-connected test client/database directly into that module
    before creating the app sidesteps the need for lifespan to run,
    mirroring eventos-service's tests/conftest.py.
    """
    settings = get_settings()
    original_db = settings.mongodb_database
    original_collection = settings.mongodb_collection

    settings.mongodb_database = "eventflow_test"
    settings.mongodb_collection = "usuarios"

    import src.services.mongodb as mongodb_module
    mongodb_module._database = test_db
    mongodb_module._client = test_db.client
    await mongodb_module.create_indexes()

    fastapi_app = create_app()

    yield fastapi_app

    settings.mongodb_database = original_db
    settings.mongodb_collection = original_collection


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
