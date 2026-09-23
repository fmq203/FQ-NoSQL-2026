"""Chain of Responsibility validators/handlers for Reservas Service."""
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from .handler import Handler, BaseHandler
from ..models.reserva import ReservaContext, SagaStep, EventType
from ..services.http_clients import get_usuario, get_evento
from ..services.redis_pago import ejecutar_pagar_y_decrementar, ejecutar_compensar_pago_inventario
from ..services.mongo import get_reservas_collection
from ..services.postgresql import insert_event_log
from ..services.metrics import (
    record_saga_step_duration,
    record_saga_total,
    record_saga_compensation,
    record_db_operation_duration,
)
from ..utils.idempotency import generate_confirmation_number
import logging
import time

logger = logging.getLogger(__name__)


class ValidadorDeDatos(BaseHandler):
    """Handler 1: Validar UUIDs, cantidad>0, metodo_pago en enum."""

    def __init__(self):
        super().__init__()
        self._step_name = SagaStep.VALIDAR_DATOS

    async def _process(self, context: ReservaContext) -> None:
        """Validar datos de entrada."""
        start_time = time.perf_counter()
        status = "success"
        try:
            # Validar UUIDs
            try:
                UUID(str(context.usuario_id))
                UUID(str(context.evento_id))
            except ValueError:
                context.error = "UUID inválido"
                context.status_code = 400
                self._add_saga_log(context, self._step_name, False, "UUID inválido")
                status = "validation_error"
                return

            # Validar cantidad > 0
            if context.cantidad <= 0:
                context.error = "Cantidad debe ser mayor a 0"
                context.status_code = 400
                self._add_saga_log(context, self._step_name, False, "Cantidad inválida")
                status = "validation_error"
                return

            # Validar metodo_pago
            valid_metodos = ["tarjeta", "transferencia", "efectivo", "mercadopago"]
            if context.metodo_pago not in valid_metodos:
                context.error = f"Método de pago inválido. Válidos: {valid_metodos}"
                context.status_code = 400
                self._add_saga_log(context, self._step_name, False, "Método pago inválido")
                status = "validation_error"
                return

            self._add_saga_log(context, self._step_name, True, "Datos válidos")
        finally:
            duration = time.perf_counter() - start_time
            record_saga_step_duration(self._step_name.value, status, duration)


class ValidadorInventario(BaseHandler):
    """Handler 2: GET Usuarios Service, verifica usuario existe."""

    def __init__(self):
        super().__init__()
        self._step_name = SagaStep.VALIDAR_USUARIO

    async def _process(self, context: ReservaContext) -> None:
        """Validar que usuario existe."""
        start_time = time.perf_counter()
        status = "success"
        try:
            usuario = await get_usuario(str(context.usuario_id), str(context.correlation_id))
            if not usuario:
                context.error = "Usuario no encontrado"
                context.status_code = 404
                self._add_saga_log(context, self._step_name, False, "Usuario no encontrado")
                status = "not_found"
                return

            context.usuario_data = usuario
            self._add_saga_log(context, self._step_name, True, f"Usuario validado: {usuario.get('nombre', '')}")

            # Emit event
            db_start = time.perf_counter()
            await insert_event_log(
                event_type=EventType.USUARIO_VALIDADO,
                aggregate_id=context.reserva_id,
                payload={"usuario_id": str(context.usuario_id), "nombre": usuario.get("nombre", "")},
                correlation_id=context.correlation_id
            )
            record_db_operation_duration("postgresql", "insert", "success", time.perf_counter() - db_start)
        except Exception as e:
            context.error = "Error validando usuario"
            context.status_code = 503
            self._add_saga_log(context, self._step_name, False, f"Error servicio usuarios: {e}")
            status = "service_error"
        finally:
            duration = time.perf_counter() - start_time
            record_saga_step_duration(self._step_name.value, status, duration)


class ValidadorEvento(BaseHandler):
    """Handler 3: GET Eventos Service, verifica existe + aforo>=cantidad."""

    def __init__(self):
        super().__init__()
        self._step_name = SagaStep.VALIDAR_EVENTO

    async def _process(self, context: ReservaContext) -> None:
        """Validar evento y aforo."""
        start_time = time.perf_counter()
        status = "success"
        try:
            evento = await get_evento(str(context.evento_id), str(context.correlation_id))
            if not evento:
                context.error = "Evento no encontrado"
                context.status_code = 404
                self._add_saga_log(context, self._step_name, False, "Evento no encontrado")
                status = "not_found"
                return

            # Verificar estado publicado
            if evento.get("estado") != "publicado":
                context.error = "Evento no disponible para reservas"
                context.status_code = 409
                self._add_saga_log(context, self._step_name, False, "Evento no publicado")
                status = "unavailable"
                return

            # Verificar aforo
            aforo_disponible = evento.get("entradas_disponibles", 0)
            if aforo_disponible < context.cantidad:
                context.error = "Inventario insuficiente"
                context.status_code = 409
                self._add_saga_log(context, self._step_name, False,
                    f"Inventario insuficiente. Disponibles: {aforo_disponible}")
                status = "insufficient_inventory"
                return

            context.evento_data = evento
            self._add_saga_log(context, self._step_name, True,
                f"Evento validado, aforo disponible: {aforo_disponible}")

            # Emit event
            db_start = time.perf_counter()
            await insert_event_log(
                event_type=EventType.EVENTO_VALIDADO,
                aggregate_id=context.reserva_id,
                payload={"evento_id": str(context.evento_id), "aforo_disponible": aforo_disponible},
                correlation_id=context.correlation_id
            )
            record_db_operation_duration("postgresql", "insert", "success", time.perf_counter() - db_start)
        except Exception as e:
            context.error = "Error validando evento"
            context.status_code = 503
            self._add_saga_log(context, self._step_name, False, f"Error servicio eventos: {e}")
            status = "service_error"
        finally:
            duration = time.perf_counter() - start_time
            record_saga_step_duration(self._step_name.value, status, duration)


class ProcesadorPago(BaseHandler):
    """Handler 4: Ejecuta Lua script pagar_y_decrementar.lua en Redis."""

    def __init__(self):
        super().__init__()
        self._step_name = SagaStep.PROCESAR_PAGO

    async def _process(self, context: ReservaContext) -> None:
        """Procesar pago y decrementar inventario atómicamente."""
        start_time = time.perf_counter()
        status = "success"
        try:
            # Calcular monto (precio * cantidad)
            # En producción, el precio vendría del evento_data
            precio_unitario = 50.0  # placeholder
            monto_total = precio_unitario * context.cantidad

            result = await ejecutar_pagar_y_decrementar(
                evento_id=str(context.evento_id),
                reserva_id=str(context.reserva_id),
                usuario_id=str(context.usuario_id),
                cantidad=context.cantidad,
                monto=monto_total,
                metodo_pago=context.metodo_pago
            )
            record_db_operation_duration("redis", "evalsha", "success" if result["success"] else "failed", 0)

            if not result["success"]:
                context.error = result["message"]
                context.status_code = 409 if "INSUFICIENTE" in result["message"] else 500
                self._add_saga_log(context, self._step_name, False, result["message"])
                status = "insufficient_inventory" if "INSUFICIENTE" in result["message"] else "payment_failed"
                return

            context.pago_data = {
                "reserva_id": str(context.reserva_id),
                "monto": monto_total,
                "metodo_pago": context.metodo_pago,
                "estado": "confirmado"
            }
            self._add_saga_log(context, self._step_name, True,
                f"Pago procesado: {monto_total}")

            # Emit event
            db_start = time.perf_counter()
            await insert_event_log(
                event_type=EventType.PAGO_PROCESADO,
                aggregate_id=context.reserva_id,
                payload={"monto": monto_total, "metodo_pago": context.metodo_pago},
                correlation_id=context.correlation_id
            )
            record_db_operation_duration("postgresql", "insert", "success", time.perf_counter() - db_start)

            # Emit inventory decremented event
            db_start = time.perf_counter()
            await insert_event_log(
                event_type=EventType.INVENTARIO_DECREMENTADO,
                aggregate_id=context.reserva_id,
                payload={"evento_id": str(context.evento_id), "cantidad": context.cantidad},
                correlation_id=context.correlation_id
            )
            record_db_operation_duration("postgresql", "insert", "success", time.perf_counter() - db_start)
        except Exception as e:
            context.error = f"Error procesando pago: {e}"
            context.status_code = 500
            self._add_saga_log(context, self._step_name, False, str(e))
            status = "error"
        finally:
            duration = time.perf_counter() - start_time
            record_saga_step_duration(self._step_name.value, status, duration)


class ConfirmadorReserva(BaseHandler):
    """Handler 5: INSERT MongoDB reserva con saga_log parcial."""

    def __init__(self):
        super().__init__()
        self._step_name = SagaStep.CONFIRMAR_RESERVA

    async def _process(self, context: ReservaContext) -> None:
        """Confirmar reserva en MongoDB."""
        start_time = time.perf_counter()
        status = "success"
        try:
            # Verificar idempotencia
            collection = await get_reservas_collection()
            db_start = time.perf_counter()
            existing = await collection.find_one({"_id": context.reserva_id})
            record_db_operation_duration("mongodb", "find_one", "success", time.perf_counter() - db_start)
            if existing:
                context.reserva_data = existing
                self._add_saga_log(context, self._step_name, True, "Reserva existente (idempotente)")
                return

            # Generar numero_confirmacion
            numero_confirmacion = generate_confirmation_number(context.reserva_id)

            # Preparar documento
            reserva_doc = {
                "_id": context.reserva_id,
                "usuario_id": context.usuario_id,
                "evento_id": context.evento_id,
                "cantidad": context.cantidad,
                "metodo_pago": context.metodo_pago,
                "monto_total": context.pago_data.get("monto", 0) if context.pago_data else 0,
                "numero_confirmacion": numero_confirmacion,
                "estado": "confirmada",
                "creado_en": datetime.utcnow(),
                "saga_log": context.saga_log + [
                    {"paso": "RESERVA_CONFIRMADA", "timestamp": datetime.utcnow().isoformat() + "Z", "exitoso": True}
                ]
            }

            db_start = time.perf_counter()
            await collection.insert_one(reserva_doc)
            record_db_operation_duration("mongodb", "insert_one", "success", time.perf_counter() - db_start)

            context.reserva_data = {
                "reserva_id": str(context.reserva_id),
                "numero_confirmacion": numero_confirmacion,
                "estado": "confirmada"
            }

            self._add_saga_log(context, "RESERVA_CONFIRMADA", True,
                f"Reserva confirmada: {reserva_doc['numero_confirmacion']}")

            # Emit event
            await insert_event_log(
                event_type=EventType.RESERVA_CONFIRMADA,
                aggregate_id=context.reserva_id,
                payload={
                    "reserva_id": str(context.reserva_id),
                    "numero_confirmacion": numero_confirmacion,
                    "cantidad": context.cantidad,
                    "monto_total": reserva_doc["monto_total"]
                },
                correlation_id=context.correlation_id
            )
        except Exception as e:
            # Compensación: rollback en Redis
            await ejecutar_compensar_pago_inventario(
                evento_id=str(context.evento_id),
                reserva_id=str(context.reserva_id),
                cantidad=context.cantidad
            )

            # Registrar compensación en PG
            db_start = time.perf_counter()
            await insert_event_log(
                event_type="COMPENSACION_EJECUTADA",
                aggregate_id=context.reserva_id,
                payload={"paso_compensado": "PAGO_PROCESADO", "accion": "INCRBY+DEL", "resultado": "OK"},
                correlation_id=context.correlation_id
            )
            record_db_operation_duration("postgresql", "insert", "success", time.perf_counter() - db_start)
            record_saga_compensation(self._step_name.value)

            context.error = f"Error confirmando reserva: {e}"
            context.status_code = 500
            self._add_saga_log(context, self._step_name, False, str(e))
            context.compensation_triggered = True
            status = "compensated"
        finally:
            duration = time.perf_counter() - start_time
            record_saga_step_duration(self._step_name.value, status, duration)


class Auditor(BaseHandler):
    """Handler 6: INSERT PostgreSQL event_log (SAGA_COMPLETED + pasos previos)."""

    def __init__(self):
        super().__init__()
        self._step_name = SagaStep.AUDITAR

    async def _process(self, context: ReservaContext) -> None:
        """Auditar SAGA completada en PostgreSQL."""
        start_time = time.perf_counter()
        status = "success"
        try:
            db_start = time.perf_counter()
            await insert_event_log(
                event_type="SAGA_COMPLETED",
                aggregate_id=context.reserva_id,
                payload={"pasos_completados": 6, "reserva_id": str(context.reserva_id)},
                correlation_id=context.correlation_id
            )
            record_db_operation_duration("postgresql", "insert", "success", time.perf_counter() - db_start)
            self._add_saga_log(context, "SAGA_COMPLETED", True, "SAGA completada y auditada")
        except Exception as e:
            # Fallo en auditoría NO rompe la reserva (warning only)
            logger.warning(f"Auditoría falló pero reserva confirmada: {e}")
            self._add_saga_log(context, "AUDITORIA", False, f"Warning: {e}")
            status = "audit_failed"
        finally:
            duration = time.perf_counter() - start_time
            record_saga_step_duration(self._step_name.value, status, duration)


class ChainBuilder:
    """Construye la cadena de handlers en orden."""

    @staticmethod
    def build() -> Handler:
        """Construye la cadena completa de handlers."""
        # Crear handlers
        validador_datos = ValidadorDeDatos()
        validador_inventario = ValidadorInventario()
        validador_evento = ValidadorEvento()
        procesador_pago = ProcesadorPago()
        confirmador_reserva = ConfirmadorReserva()
        auditor = Auditor()

        # Encadenar: 1→2→3→4→5→6
        validador_datos.set_next(validador_inventario)
        validador_inventario.set_next(validador_evento)
        validador_evento.set_next(procesador_pago)
        procesador_pago.set_next(confirmador_reserva)
        confirmador_reserva.set_next(auditor)

        return validador_datos