# EventFlow — Sistema de Microservicios para Gestión de Eventos

**Tarea 2 NoSQL** — Diseño e implementación de un sistema de microservicios con múltiples bases de datos NoSQL.

---

## 📋 Descripción del Proyecto

**EventFlow** es una plataforma ficticia de gestión y venta de entradas para eventos. El objetivo es implementar una arquitectura de microservicios que maneje:

- ✅ Alto volumen de **lecturas** (eventos, usuarios)
- ✅ **Transacciones atómicas** (pagos, reservas)
- ✅ **Auditoría legal** (compliance, GDPR)

### Características Principales

- **3 Bases de Datos NoSQL** (especialización por caso de uso)
  - MongoDB: datos de negocio (usuarios, eventos)
  - Redis: transacciones atómicas (pagos)
  - PostgreSQL: auditoría e cumplimiento legal

- **2 Patrones de Diseño** (SAGA + Chain of Responsibility)
  - SAGA Orchestration: orquesta transacciones distribuidas
  - Chain of Responsibility: validaciones modulares

- **Contenedorización** (Docker + Docker Compose)

---

## 🏗️ Arquitectura

```
                   EVENTFLOW 3-DATABASE ARCHITECTURE

┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  MONGODB         │    │  REDIS          │    │  POSTGRESQL      │
│  (Datos maestros)│    │  (Transacciones)│    │  (Auditoría)     │
├──────────────────┤    ├─────────────────┤    ├──────────────────┤
│ • Usuarios       │    │ • Pagos (atomic)│    │ • Event Log      │
│ • Eventos        │    │ • Reservas temp │    │   (immutable)    │
│ • Historial      │    │ • Caché         │    │ • Compliance     │
│ • Escalable      │    │ • Ultra-rápido  │    │ • GDPR Tracking  │
└──────────────────┘    └─────────────────┘    └──────────────────┘
     AP (Eventual)          CP (Strong)            CA (ACID logs)
```

### Microservicios

1. **Usuarios Service** (puerto 8001)
   - Gestiona perfiles de usuarios
   - BD: MongoDB

2. **Eventos Service** (puerto 8002)
   - Gestiona información de eventos
   - BD: MongoDB

3. **Reservas & Pagos Service** (puerto 8003)
   - Orquestador SAGA
   - Procesa compras de entradas
   - BD: Redis (pagos), MongoDB (confirmación), PostgreSQL (auditoría)

---

## 🚀 Quick Start

### Requisitos

- Python 3.11+
- Docker & Docker Compose
- Git

### Instalación

```bash
# 1. Clonar repositorio
git clone <repo>
cd "NoSQL/TAREA 2"

# 2. Crear virtual env
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env

# 5. Iniciar bases de datos
docker-compose up -d

# 6. Iniciar servicios (en terminales separadas)
cd usuarios-service && uvicorn src.main:app --reload
cd eventos-service && uvicorn src.main:app --reload
cd reservas-service && uvicorn src.main:app --reload
```

### Iniciar Todo con Docker Compose

```bash
# Construir y iniciar todos los servicios
docker-compose up --build

# Ver logs
docker-compose logs -f

# Parar servicios
docker-compose down
```

---

## 📡 Endpoints

### Usuarios Service (8001)

```bash
POST /api/usuarios              # Crear usuario
GET /api/usuarios/{usuario_id}  # Obtener usuario
GET /api/usuarios               # Listar usuarios (paginado)
GET /api/usuarios/exportar      # Exportar datos anonimizados
GET /docs                        # Swagger UI
```

### Eventos Service (8002)

```bash
POST /api/eventos               # Crear evento
GET /api/eventos/{evento_id}    # Obtener evento
GET /docs                        # Swagger UI
```

### Reservas & Pagos Service (8003)

```bash
POST /api/reservar              # Crear reserva (SAGA + pagos)
GET /docs                        # Swagger UI
```

### Health Check

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

---

## 🔍 Testing

### Con Swagger UI

```
http://localhost:8001/docs  → Usuarios
http://localhost:8002/docs  → Eventos
http://localhost:8003/docs  → Reservas
```

### Con cURL

```bash
# Crear usuario
curl -X POST http://localhost:8001/api/usuarios \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_documento": "DNI",
    "nro_documento": "12345678",
    "nombre": "Juan",
    "apellido": "Pérez",
    "email": "juan@example.com"
  }'

# Crear evento
curl -X POST http://localhost:8002/api/eventos \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Concierto 2026",
    "fecha": "2026-12-15T20:00:00Z",
    "lugar": "Estadio Nacional",
    "aforo_total": 50000,
    "precio_entrada": 150.00
  }'

# Crear reserva
curl -X POST http://localhost:8003/api/reservar \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "uuid-aquí",
    "evento_id": "uuid-aquí",
    "cantidad": 2,
    "metodo_pago": "tarjeta_credito"
  }'
```

---

## 📚 Documentación Completa

Para documentación detallada, arquitectura y decisiones de diseño:

```
brain/  ← Segundo cerebro del proyecto
├── CLAUDE.md           ← Mapa principal
├── index.md            ← Catálogo de docs
├── decisions/          ← Justificación de decisiones
├── architecture/       ← Diagramas y overview
├── patterns/           ← SAGA, Chain of Responsibility, Event Log
├── data-models/        ← Schemas MongoDB, Redis, PostgreSQL
└── ...
```

**Leer primero:** `brain/README.md`

---

## 🔧 Tecnologías

- **Framework:** FastAPI (Python)
- **BDs NoSQL:** MongoDB, Redis, PostgreSQL
- **ORM/Drivers:** pymongo, redis-py, psycopg
- **Contenedorización:** Docker, Docker Compose
- **API Docs:** Swagger UI (spec-kit)
- **Testing:** pytest

---

## 📊 Estructura de Carpetas

```
.
├── brain/                    ← Documentación arquitectónica
│   ├── CLAUDE.md
│   ├── decisions/
│   ├── architecture/
│   ├── patterns/
│   ├── data-models/
│   ├── endpoints/
│   └── deployment/
│
├── usuarios-service/         ← Servicio de Usuarios
│   ├── src/
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── eventos-service/          ← Servicio de Eventos
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── reservas-service/         ← Servicio de Reservas (Orquestador)
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── .github/
│   └── workflows/            ← CI/CD pipelines (GitHub Actions)
│
├── docker-compose.yml        ← Orquestación local
├── requirements.txt          ← Dependencias Python
├── .env.example              ← Variables de entorno
├── .gitignore
└── README.md                 ← Este archivo
```

---

## 🔗 Flujo de Compra (SAGA)

```
1. POST /api/reservar
   │
   ├─ SAGA Step 1: Validar Usuario (MongoDB)
   ├─ SAGA Step 2: Validar Evento (MongoDB)
   ├─ SAGA Step 3: Procesar Pago (Redis atomic)
   ├─ SAGA Step 4: Decrement Inventario (MongoDB)
   ├─ SAGA Step 5: Confirmar en MongoDB
   │
   └─ PostgreSQL: Registrar evento en log (auditoría)

   ✅ Éxito → 201 Created
   ❌ Fallo → Compensaciones + Rollback
```

---

## 🧪 Testing

```bash
# Instalar dependencias de testing
pip install pytest pytest-asyncio pytest-cov

# Ejecutar tests
pytest

# Con coverage
pytest --cov=usuarios_service --cov=eventos_service --cov=reservas_service
```

---

## 🚢 Despliegue

### Local (Docker Compose)

```bash
docker-compose up --build
```

### Kubernetes (Opcional)

```bash
# Generar manifests desde docker-compose
kompose convert -f docker-compose.yml -o k8s/

# Aplicar en cluster
kubectl apply -f k8s/
```

---

## 🔐 Variables de Entorno

Ver `.env.example` para lista completa. Copiar a `.env` y configurar:

```bash
cp .env.example .env
# Editar .env con valores locales
```

---

## 📅 Fechas de Entrega

- **Pre-defensa:** Jueves 5 de noviembre
- **Defensa final:** Jueves 12 de noviembre
- **Presentación:** ~12 minutos (demo + arquitectura)

---

## 👥 Equipo

- (Agregar nombres del grupo)

---

## 📖 Referencias

- [[brain/decisions/three-database-strategy.md]] — Por qué 3 BDs
- [[brain/patterns/saga-pattern.md]] — Patrón SAGA explicado
- [[brain/patterns/event-log-pattern.md]] — Event Log para auditoría
- [[brain/deployment/spec-kit-setup.md]] — OpenAPI automático

---

## 📞 Ayuda

Si algo no funciona:

1. Ver `docker-compose logs` (para errores de BD)
2. Ver `requirements.txt` (dependencias)
3. Consultar `brain/README.md` (documentación completa)
4. Revisar `.env` (variables de entorno)

---

**Última actualización:** 2026-09-20
