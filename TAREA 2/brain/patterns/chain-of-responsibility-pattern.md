---
name: chain-of-responsibility-pattern
description: Implementación del patrón Chain of Responsibility para validaciones
metadata:
  type: pattern
  status: in-progress
---

# Patrón Chain of Responsibility

## Objetivo

Estructurar una serie de validaciones y procesamiento de solicitudes de reserva de forma modular y extensible.

---

## Diseño: Cadena de Manejadores

```
Solicitud de Reserva
    │
    ▼
┌──────────────────────────────────┐
│ 1. ValidadorDatos                │
│ - Verifica: usuario_id existe    │
│ - Verifica: evento_id existe     │
│ - Verifica: cantidad > 0          │
└────────┬─────────────────────────┘
         │ ✅ Pass → Siguiente
         │
         ▼
┌──────────────────────────────────┐
│ 2. ValidadorInventario           │
│ - Verifica: entradas disponibles │
│ - Valida: cantidad <= disponibles│
└────────┬─────────────────────────┘
         │ ✅ Pass → Siguiente
         │
         ▼
┌──────────────────────────────────┐
│ 3. ValidadorPago                 │
│ - Verifica: datos de pago válidos│
│ - Verifica: tarjeta activa       │
└────────┬─────────────────────────┘
         │ ✅ Pass → Siguiente
         │
         ▼
┌──────────────────────────────────┐
│ 4. ProcesadorDePago              │
│ - Procesa transacción en Redis   │
│ - Registra en MongoDB            │
└────────┬─────────────────────────┘
         │
         ▼
    Reserva Confirmada O ❌ Error
```

---

## Implementación: Pseudocódigo

```python
# Interfaz base
class Validador(ABC):
    def __init__(self, siguiente=None):
        self.siguiente = siguiente
    
    def procesar(self, solicitud):
        if self.validar(solicitud):
            if self.siguiente:
                return self.siguiente.procesar(solicitud)
            else:
                return self.finalizar(solicitud)
        else:
            raise ValidationError(self.mensaje_error)
    
    @abstractmethod
    def validar(self, solicitud):
        pass
    
    @abstractmethod
    def finalizar(self, solicitud):
        pass

# ============ MANEJADORES ============

class ValidadorDatos(Validador):
    def validar(self, solicitud):
        return (
            solicitud.usuario_id and
            solicitud.evento_id and
            solicitud.cantidad > 0
        )
    
    def finalizar(self, solicitud):
        # Si es el último en la cadena
        pass

class ValidadorInventario(Validador):
    def __init__(self, eventos_service, siguiente=None):
        super().__init__(siguiente)
        self.eventos_service = eventos_service
    
    def validar(self, solicitud):
        evento = self.eventos_service.get(solicitud.evento_id)
        return evento.entradas_disponibles >= solicitud.cantidad
    
    @property
    def mensaje_error(self):
        return "Inventario insuficiente"

class ValidadorPago(Validador):
    def validar(self, solicitud):
        # Validar formato de tarjeta, fecha, etc.
        return (
            len(solicitud.datos_pago['numero_tarjeta']) == 16 and
            solicitud.datos_pago['cvv'] and
            self.tarjeta_valida()
        )
    
    @property
    def mensaje_error(self):
        return "Datos de pago inválidos"

class ProcesadorDePago(Validador):
    def __init__(self, redis_client, mongodb_client, siguiente=None):
        super().__init__(siguiente)
        self.redis = redis_client
        self.mongodb = mongodb_client
    
    def validar(self, solicitud):
        # Procesar en Redis (Lua script)
        try:
            resultado = self.redis.execute_lua_script(
                SCRIPT_PROCESAR_PAGO,
                solicitud
            )
            solicitud.reserva_id = resultado['reserva_id']
            return resultado['ok']
        except:
            return False
    
    def finalizar(self, solicitud):
        # Registrar en MongoDB
        self.mongodb.reservas.insert_one({
            'reserva_id': solicitud.reserva_id,
            'usuario_id': solicitud.usuario_id,
            'evento_id': solicitud.evento_id,
            'estado': 'confirmada'
        })
        return {'status': 'éxito', 'reserva_id': solicitud.reserva_id}

# ============ CONSTRUCCIÓN ============

def construir_cadena_reservas(eventos_service, redis_client, mongodb_client):
    return ValidadorDatos(
        siguiente=ValidadorInventario(
            eventos_service,
            siguiente=ValidadorPago(
                siguiente=ProcesadorDePago(redis_client, mongodb_client)
            )
        )
    )

# ============ USO ============

cadena = construir_cadena_reservas(...)

try:
    resultado = cadena.procesar(solicitud_reserva)
    return {'status': 201, 'data': resultado}
except ValidationError as e:
    return {'status': 400, 'error': str(e)}
```

---

## Ventajas del Patrón

| Ventaja | Descripción |
|---------|------------|
| **Modularidad** | Cada validador es independiente |
| **Extensibilidad** | Fácil agregar nuevos validadores |
| **Responsabilidad Única** | Cada handler hace una cosa |
| **Reusabilidad** | Handlers se pueden reutilizar en otras cadenas |
| **Testing** | Cada handler se puede testear aisladamente |

---

## Validadores en EventFlow

### 1. ValidadorDatos
- ✅ usuario_id existe
- ✅ evento_id existe
- ✅ cantidad > 0 y <= límite

### 2. ValidadorInventario
- ✅ Evento tiene entradas disponibles
- ✅ Cantidad solicitada <= disponibles

### 3. ValidadorPago
- ✅ Tarjeta válida (Luhn check)
- ✅ Fecha de expiración válida
- ✅ CVV presente

### 4. ProcesadorDePago
- ✅ Redis Lua script (transacción atómica)
- ✅ Retorna reserva_id

### 5. ConfirmadorTransaccion (Opcional)
- ✅ Registro final en MongoDB
- ✅ Event logging para auditoria

---

## Composición: CoR + SAGA

```
Chain of Responsibility (Validaciones)
         │
         ▼ (Todo validado)
    SAGA Orchestrator (Ejecución distribuida)
         │
         ├─ Step 1: Llamar APIs
         ├─ Step 2: Procesar pago
         ├─ Step 3: Actualizar inventario
         └─ Step 4: Registrar resultado
         │
         ▼ (Success o Compensaciones)
    Respuesta al cliente
```

---

## Ejemplo de Error Handling

```python
solicitud = ReservaRequest(
    usuario_id="usuario123",
    evento_id="evento456",
    cantidad=2
)

try:
    resultado = cadena.procesar(solicitud)
except ValidationError as e:
    if e.tipo == "datos":
        return 400, "Datos inválidos"
    elif e.tipo == "inventario":
        return 409, "No hay entradas disponibles"
    elif e.tipo == "pago":
        return 402, "Pago rechazado"
```

---

## Próximos Pasos

- [ ] Implementar cada validador
- [ ] Testing de cadena completa
- [ ] Logging en cada punto
- [ ] Métricas de validación
