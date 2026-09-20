# Guía de Contribución — EventFlow

## 🎯 Antes de Empezar

1. **Lee el README.md** — Entiende la arquitectura
2. **Lee brain/README.md** — Entiende decisiones de diseño
3. **Revisa brain/microservices/** — Tu servicio específico

## 🔄 Flujo de Trabajo

### 1. Elige tu Tarea

```
- Usuarios Service (puerto 8001)
- Eventos Service (puerto 8002)
- Reservas Service (puerto 8003, crítico)
```

### 2. Implementa según Brain

Cada servicio tiene una guía en `brain/`:

```
brain/microservices/usuarios.md
brain/endpoints/usuarios-endpoints.md
brain/data-models/user-schema.md
```

### 3. Sigue Spec-kit para APIs

```python
# Ejemplo: usuarios-service/src/main.py

from fastapi import FastAPI

app = FastAPI(
    title="Usuarios Service",
    version="1.0.0"
)

@app.get("/api/usuarios/{usuario_id}")
async def obtener_usuario(usuario_id: UUID):
    """
    Obtener usuario por ID
    
    Retorna usuario con historial de compras.
    """
    # Implementar aquí
    pass
```

### 4. Generar spec.json

```bash
cd usuarios-service
spec-kit generate --output spec.json
```

### 5. Probar en Swagger UI

```
http://localhost:8001/docs
```

## 📋 Checklist por Servicio

### Usuarios Service

- [ ] POST /api/usuarios → crear usuario
- [ ] GET /api/usuarios → listar (paginado)
- [ ] GET /api/usuarios/{id} → obtener usuario
- [ ] GET /api/usuarios/exportar → exportar anonimizado
- [ ] spec.json generado
- [ ] Tests unitarios
- [ ] Dockerfile funciona

### Eventos Service

- [ ] POST /api/eventos → crear evento
- [ ] GET /api/eventos/{id} → obtener evento
- [ ] spec.json generado
- [ ] Tests unitarios
- [ ] Dockerfile funciona

### Reservas Service (Crítico)

- [ ] POST /api/reservar → SAGA completo
  - [ ] Validar usuario
  - [ ] Validar evento
  - [ ] Procesar pago (Redis atomic)
  - [ ] Decrement inventario
  - [ ] Confirmar en MongoDB
  - [ ] Auditoría en PostgreSQL
- [ ] Compensaciones (rollback)
- [ ] spec.json generado
- [ ] Tests SAGA
- [ ] Dockerfile funciona

## 🧪 Testing

### Local (sin Docker)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Iniciar bases de datos en Docker
docker-compose up -d mongodb redis postgresql

# Iniciar servicio
cd usuarios-service
uvicorn src.main:app --reload

# En otra terminal, testear
python -m pytest tests/
```

### Con Docker

```bash
# Construir y iniciar todo
docker-compose up --build

# Ver logs
docker-compose logs -f usuarios-service
```

## 📝 Código

### Estilo

- Use **type hints** (PEP 484)
- Use **docstrings** en funciones
- Use **camelCase** para variables, **UPPER_CASE** para constantes
- Máximo 88 caracteres por línea (black)

### Ejemplo

```python
from uuid import UUID
from datetime import datetime

async def obtener_usuario(usuario_id: UUID) -> dict:
    """
    Obtener usuario por ID desde MongoDB.
    
    Args:
        usuario_id: UUID del usuario
    
    Returns:
        dict con datos del usuario
    
    Raises:
        HTTPException: Si usuario no existe (404)
    """
    usuario = db.usuarios.find_one({"_id": usuario_id})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario
```

## 🔗 Comunicación entre Servicios

Usar `httpx` para llamadas inter-servicio:

```python
import httpx

async def obtener_usuario_externo(usuario_id: UUID):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://usuarios-service:8001/api/usuarios/{usuario_id}"
        )
        if response.status_code != 200:
            raise Exception("Usuario no encontrado")
        return response.json()
```

## 📊 Bases de Datos

### MongoDB (Usuarios, Eventos)

```python
from pymongo import MongoClient

client = MongoClient("mongodb://mongodb:27017")
db = client["eventflow"]

# Crear usuario
db.usuarios.insert_one({
    "_id": usuario_id,
    "nombre": "Juan",
    "email": "juan@example.com"
})

# Buscar usuario
usuario = db.usuarios.find_one({"_id": usuario_id})
```

### Redis (Pagos)

```python
import redis

redis_client = redis.from_url("redis://redis:6379")

# Operación atómica (Lua script)
script = """
if redis.call('GET', KEYS[1]) >= ARGV[1] then
  redis.call('DECR', KEYS[1])
  return 1
else
  return 0
end
"""

resultado = redis_client.eval(script, 1, "evento:123", 1)
```

### PostgreSQL (Auditoría)

```python
import psycopg

conn = psycopg.connect("postgresql://user:pass@postgresql:5432/eventflow")
cur = conn.cursor()

# Registrar evento
cur.execute("""
  INSERT INTO event_log (evento_id, tipo, usuario_id, datos, timestamp)
  VALUES (%s, %s, %s, %s, NOW())
""", (evento_id, "RESERVA_CREADA", usuario_id, json.dumps(datos)))

conn.commit()
```

## 🐳 Docker

### Construir servicio local

```bash
cd usuarios-service
docker build -t usuarios-service:latest .
```

### Ver logs

```bash
docker-compose logs -f usuarios-service
```

### Resetear todo

```bash
docker-compose down -v  # -v elimina volúmenes (BD)
docker-compose up --build
```

## 🔍 Debugging

### Ver requests/responses

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Probar endpoint

```bash
curl -X POST http://localhost:8001/api/usuarios \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Juan","email":"juan@example.com"}'
```

### Ver estado de BDs

```bash
# MongoDB
docker exec eventflow_mongodb mongosh --eval "db.usuarios.find().limit(5)"

# Redis
docker exec eventflow_redis redis-cli KEYS "*"

# PostgreSQL
docker exec eventflow_postgresql psql -U eventflow_user -d eventflow -c "SELECT * FROM event_log LIMIT 5"
```

## 📚 Documentación

- **README.md** — Visión general
- **brain/README.md** — Decisiones arquitectónicas
- **brain/microservices/** — Spec de tu servicio
- **brain/patterns/** — Cómo implementar SAGA, Chain of Responsibility
- **brain/data-models/** — Schemas de BDs

## 🚀 Preguntas Frecuentes

**P: ¿Cómo genero spec.json?**
R: `spec-kit generate --output spec.json` en el directorio del servicio

**P: ¿Cómo testeo inter-servicio?**
R: Ver ejemplos en `brain/patterns/saga-pattern.md`

**P: ¿Cómo implemento SAGA?**
R: Ver `brain/patterns/saga-pattern.md` (paso a paso)

**P: ¿Dónde registro auditoría?**
R: PostgreSQL `event_log` table (ver `brain/patterns/event-log-pattern.md`)

## 💡 Tips

- Mantén servicios **stateless** (escalables)
- Usa **health checks** (`/health` endpoint)
- Loguea con **niveles** (DEBUG, INFO, ERROR)
- Testea **en Docker**, no solo local
- Valida **inputs** (Pydantic models)
- Maneja **errores gracefully** (no crashes)

---

**¿Preguntas?** Consulta `brain/README.md` o abre un issue.
