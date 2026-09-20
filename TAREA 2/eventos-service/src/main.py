"""
Eventos Service - EventFlow
Gestión de eventos y disponibilidad de entradas.

Ver: brain/microservices/eventos.md
"""
from fastapi import FastAPI
import os

app = FastAPI(
    title="Eventos Service",
    version="1.0.0"
)

SERVICE_PORT = int(os.getenv("SERVICE_PORT", 8002))

@app.get("/health")
async def health():
    return {"status": "ok", "service": "eventos"}

@app.post("/api/eventos")
async def crear_evento(evento: dict):
    """Crear nuevo evento - TODO: Implementar"""
    # Ver brain/endpoints/eventos-endpoints.md para spec
    return {"evento_id": "..."}

@app.get("/api/eventos/{evento_id}")
async def obtener_evento(evento_id: str):
    """Obtener evento por ID - TODO: Implementar"""
    return {}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
