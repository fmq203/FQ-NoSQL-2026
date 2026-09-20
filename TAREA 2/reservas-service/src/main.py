"""
Reservas & Pagos Service - EventFlow (Orquestador SAGA)

Procesa compras de entradas usando SAGA Orchestration.
Coordina: Usuarios Service → Eventos Service → Pagos (Redis)

Ver documentación:
- brain/patterns/saga-pattern.md          (Flujo SAGA)
- brain/patterns/chain-of-responsibility-pattern.md  (Validaciones)
- brain/microservices/reservas-pagos.md  (Especificación)
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from uuid import UUID
import os
import httpx
import redis
from pymongo import MongoClient

app = FastAPI(
    title="Reservas & Pagos Service",
    version="1.0.0",
    description="Orquestador SAGA para compra de entradas"
)

# ============ CONFIGURACIÓN ============

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
POSTGRESQL_URI = os.getenv("POSTGRESQL_URI", "postgresql://localhost:5432/eventflow")
USUARIOS_SERVICE_URL = os.getenv("USUARIOS_SERVICE_URL", "http://localhost:8001")
EVENTOS_SERVICE_URL = os.getenv("EVENTOS_SERVICE_URL", "http://localhost:8002")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", 8003))

# ============ CLIENTES ============

redis_client = redis.from_url(REDIS_URL)
mongodb_client = MongoClient(MONGODB_URI)
mongodb = mongodb_client[os.getenv("MONGODB_DB", "eventflow")]

# ============ MODELOS ============

class ReservaRequest(BaseModel):
    usuario_id: UUID
    evento_id: UUID
    cantidad: int
    metodo_pago: str

class ReservaResponse(BaseModel):
    reserva_id: str
    estado: str
    numero_confirmacion: str

# ============ ENDPOINTS ============

@app.get("/health")
async def health():
    return {"status": "ok", "service": "reservas"}

@app.post("/api/reservar", response_model=ReservaResponse, status_code=201)
async def reservar(solicitud: ReservaRequest):
    """
    Crear reserva - Inicia SAGA Orchestration

    SAGA STEPS:
    1. Validar usuario (Usuarios Service)
    2. Validar evento + inventario (Eventos Service)
    3. Procesar pago (Redis - atomic)
    4. Decrement inventario (Eventos Service)
    5. Confirmar en MongoDB
    6. Registrar en PostgreSQL (audit log)

    Si cualquier paso falla → compensaciones (rollback)

    Ver: brain/patterns/saga-pattern.md
    """

    try:
        # SAGA STEP 1: Validar usuario
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{USUARIOS_SERVICE_URL}/api/usuarios/{solicitud.usuario_id}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Usuario no encontrado")

        # SAGA STEP 2: Validar evento
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{EVENTOS_SERVICE_URL}/api/eventos/{solicitud.evento_id}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Evento no encontrado")
            evento = resp.json()
            if evento["entradas_disponibles"] < solicitud.cantidad:
                raise HTTPException(status_code=409, detail="Inventario insuficiente")

        # SAGA STEP 3: Procesar pago en Redis (ATOMIC)
        # TODO: Ejecutar Lua script en Redis para transacción atómica

        # SAGA STEP 4: Decrement inventario
        # TODO: Llamar a Eventos Service para decrementar

        # SAGA STEP 5: Confirmar en MongoDB
        # TODO: Registrar reserva en MongoDB

        # SAGA STEP 6: Auditoría en PostgreSQL
        # TODO: Registrar evento en event_log

        return ReservaResponse(
            reserva_id="res-xxx",
            estado="confirmada",
            numero_confirmacion="CONF-20260920-xxx"
        )

    except Exception as e:
        # COMPENSACIONES: revertir cambios
        # TODO: Implementar rollback automático
        raise HTTPException(status_code=500, detail="Transacción fallida")

# ============ MAIN ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
