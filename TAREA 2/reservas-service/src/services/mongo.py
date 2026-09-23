"""MongoDB connection and index management for Reservas Service."""
import os
import pymongo
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

# Global client and database instances
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None


async def get_mongo_client() -> AsyncIOMotorClient:
    """Get or create MongoDB async client with Motor."""
    global _mongo_client
    if _mongo_client is None:
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        _mongo_client = AsyncIOMotorClient(
            mongodb_uri,
            maxPoolSize=50,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            uuidRepresentation="standard",  # Handle UUID encoding
        )
    return _mongo_client


async def get_mongo_db() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance."""
    global _mongo_db
    if _mongo_db is None:
        client = await get_mongo_client()
        mongodb_db = os.getenv("MONGODB_DB", "eventflow")
        _mongo_db = client[mongodb_db]
    return _mongo_db


async def init_mongodb_indexes() -> None:
    """Create all required MongoDB indexes for reservas collection."""
    db = await get_mongo_db()
    collection = db.reservas

    indexes = [
        # Historial por usuario
        ([("usuario_id", ASCENDING), ("creado_en", DESCENDING)], "idx_usuario_fecha"),
        # Ocupación por evento
        ([("evento_id", ASCENDING), ("estado", ASCENDING)], "idx_evento_estado"),
        # Búsqueda por confirmación (único)
        ([("numero_confirmacion", ASCENDING)], {"unique": True, "name": "idx_confirmacion_unique"}),
        # Reportes por estado
        ([("estado", ASCENDING), ("creado_en", DESCENDING)], "idx_estado_fecha"),
        # TTL limpieza automática (24h para pendiente/fallida)
        ([("creado_en", ASCENDING)], {
            "expireAfterSeconds": 86400,
            "partialFilterExpression": {"estado": {"$in": ["pendiente", "fallida"]}},
            "name": "idx_ttl_pendiente_fallida"
        }),
    ]

    for index_spec in indexes:
        try:
            if isinstance(index_spec[1], dict):
                await collection.create_index(index_spec[0], **index_spec[1])
            else:
                await collection.create_index(index_spec[0], name=index_spec[1])
        except OperationFailure as e:
            # Index already exists or other non-critical error
            print(f"Warning creating index {index_spec}: {e}")


async def close_mongodb_connection() -> None:
    """Close MongoDB connection."""
    global _mongo_client, _mongo_db
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None


async def get_reservas_collection():
    """Get reservas collection with write concern majority + journal."""
    db = await get_mongo_db()
    return db.reservas.with_options(
        write_concern=pymongo.WriteConcern(w="majority", j=True)
    )