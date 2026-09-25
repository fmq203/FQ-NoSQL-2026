import pytest
import pytest_asyncio
from httpx import AsyncClient
from src.main import create_app


@pytest.fixture(autouse=True)
def _reset_db_singletons():
    """Reset every module-global connection singleton before and after each test.

    src/services/mongodb.py, mongo.py, redis_pago.py and postgresql.py all
    lazily create their client/pool the first time they're used and cache
    it in a module-level variable. That's fine in production (one process,
    one event loop, for the life of the app), but under pytest-asyncio each
    test function gets its own event loop by default - a client created in
    test A's loop is unusable once that loop is closed, and calling it from
    test B raises "RuntimeError: Event loop is closed" even though the code
    under test is correct. Clearing the singletons forces each test to
    lazily recreate whatever client it actually touches, bound to its own
    loop, instead of reusing one left over from a previous test.
    """
    import src.services.mongodb as mongodb_module
    import src.services.mongo as mongo_module
    import src.services.redis_pago as redis_pago_module
    import src.services.postgresql as postgresql_module
    import src.services.http_clients as http_clients_module

    def _reset():
        mongodb_module._client = None
        mongodb_module._database = None
        mongo_module._mongo_client = None
        mongo_module._mongo_db = None
        redis_pago_module._redis = None
        redis_pago_module._sha_reservar = None
        redis_pago_module._sha_liberar = None
        redis_pago_module._sha_pagar = None
        redis_pago_module._sha_compensar = None
        postgresql_module._pg_pool = None
        http_clients_module._usuarios_client = None
        http_clients_module._eventos_client = None

    _reset()
    yield
    _reset()


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
        "categoria": "general"
    }
