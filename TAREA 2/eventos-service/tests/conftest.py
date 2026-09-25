import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from src.main import create_app
from src.config import get_settings
import os


@pytest.fixture(scope="session")
def test_mongodb_uri():
    """Get test MongoDB URI from environment or use default"""
    return os.getenv("TEST_MONGODB_URI", "mongodb://localhost:27017")


@pytest_asyncio.fixture(scope="function")
async def test_db(test_mongodb_uri):
    """Create a test database and clean up after"""
    client = AsyncIOMotorClient(
        test_mongodb_uri,
        uuidRepresentation="standard",
    )
    db_name = "eventflow_test"
    db = client[db_name]
    
    # Drop the database to ensure clean state
    await client.drop_database(db_name)
    
    yield db
    
    # Cleanup
    await client.drop_database(db_name)
    client.close()


@pytest_asyncio.fixture
async def app(test_db):
    """Create app with test database"""
    settings = get_settings()
    # Override the database settings for tests
    original_db = settings.mongodb_database
    original_collection = settings.mongodb_collection
    
    settings.mongodb_database = "eventflow_test"
    settings.mongodb_collection = "eventos"
    
    # Force reconnection with test settings
    import src.services.mongodb as mongodb_module
    mongodb_module._database = test_db
    mongodb_module._client = test_db.client
    
    app = create_app()
    
    yield app
    
    # Restore original settings
    settings.mongodb_database = original_db
    settings.mongodb_collection = original_collection


@pytest_asyncio.fixture
async def async_client(app):
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def created_event_id(async_client):
    response = await async_client.post(
        "/api/eventos",
        json={
            "nombre": "Test Event for Get",
            "estado": "publicado",
            "aforo_total": 100,
            "entradas_disponibles": 100,
            "precios": [
                {"categoria": "General", "precio": 100.00, "disponibles": 100}
            ],
            "ubicacion": {
                "ciudad": "Buenos Aires",
                "pais": "Argentina"
            }
        }
    )
    assert response.status_code == 201
    return response.json()["evento_id"]