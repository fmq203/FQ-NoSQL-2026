"""Saga Orchestrator for Reservas Service.

Coordinates the Chain of Responsibility execution, handles errors,
and triggers compensations for failed steps.
"""
import logging
from typing import Dict, Callable, Awaitable, Optional
from src.chain.handler import Handler
from src.models.reserva import ReservaContext, SagaStep
from src.services.redis_pago import ejecutar_compensar_pago_inventario
from src.services.postgresql import insert_event_log
from src.models.reserva import EventType

logger = logging.getLogger(__name__)


class SagaOrchestrator:
    """Orchestrates SAGA execution with compensation handling."""
    
    def __init__(
        self,
        chain: Handler,
        compensation_handlers: Optional[Dict[int, Callable[[ReservaContext], Awaitable[None]]]] = None
    ):
        self.chain = chain
        self.compensation_handlers = compensation_handlers or {}
        self._step_names = {
            1: SagaStep.VALIDAR_DATOS,
            2: SagaStep.VALIDAR_USUARIO,
            3: SagaStep.VALIDAR_EVENTO,
            4: SagaStep.PROCESAR_PAGO,
            5: SagaStep.CONFIRMAR_RESERVA,
            6: SagaStep.AUDITAR,
        }
    
    async def execute(self, context: ReservaContext) -> ReservaContext:
        """Execute the complete SAGA chain with error handling and compensations."""
        logger.info(
            "Starting SAGA execution",
            extra={
                "correlation_id": str(context.correlation_id),
                "reserva_id": str(context.reserva_id),
                "operation": "saga_execute",
            }
        )
        
        try:
            # Execute the chain
            context = await self.chain.handle(context)
            
            if context.error:
                await self._handle_error(context)
            else:
                logger.info(
                    "SAGA completed successfully",
                    extra={
                        "correlation_id": str(context.correlation_id),
                        "reserva_id": str(context.reserva_id),
                        "operation": "saga_execute",
                    }
                )
            
            return context
            
        except Exception as e:
            logger.exception(
                "Unexpected error in SAGA execution",
                extra={
                    "correlation_id": str(context.correlation_id),
                    "reserva_id": str(context.reserva_id),
                }
            )
            context.error = f"Error inesperado en SAGA: {e}"
            context.status_code = 500
            await self._handle_error(context)
            return context
    
    async def _handle_error(self, context: ReservaContext) -> None:
        """Handle error by executing compensations in reverse order."""
        failed_step = self._identify_failed_step(context)
        logger.warning(
            f"SAGA failed at step {failed_step}: {context.error}",
            extra={
                "correlation_id": str(context.correlation_id),
                "reserva_id": str(context.reserva_id),
                "failed_step": failed_step,
                "operation": "saga_compensation",
            }
        )
        
        # Execute compensations in reverse order (only for mutating steps 4-5)
        compensation_steps = self._get_compensation_steps(failed_step)
        
        for step in compensation_steps:
            handler = self.compensation_handlers.get(step)
            if handler:
                try:
                    logger.info(
                        f"Executing compensation for step {step}",
                        extra={
                            "correlation_id": str(context.correlation_id),
                            "reserva_id": str(context.reserva_id),
                            "compensation_step": step,
                        }
                    )
                    await handler(context)
                    
                    # Log compensation event
                    await insert_event_log(
                        event_type="COMPENSACION_EJECUTADA",
                        aggregate_id=context.reserva_id,
                        payload={
                            "paso_compensado": self._step_names.get(step, f"STEP_{step}"),
                            "accion": "COMPENSATION",
                            "resultado": "OK"
                        },
                        correlation_id=context.correlation_id
                    )
                except Exception as e:
                    logger.error(
                        f"Compensation failed for step {step}: {e}",
                        extra={
                            "correlation_id": str(context.correlation_id),
                            "reserva_id": str(context.reserva_id),
                            "compensation_step": step,
                        }
                    )
    
    def _identify_failed_step(self, context: ReservaContext) -> int:
        """Identify which step failed based on context."""
        # Check saga_log for the last failed step
        for entry in reversed(context.saga_log):
            if not entry.get("exitoso", True):
                # Map step name to step number
                step_name = entry.get("paso", "")
                for num, name in self._step_names.items():
                    if name == step_name:
                        return num
        # Default to step 5 if we can't determine
        return 5
    
    def _get_compensation_steps(self, failed_step: int) -> list:
        """Get list of steps to compensate in reverse order."""
        # Only steps 4 and 5 have compensations (mutating steps)
        compensation_steps = []
        for step in range(failed_step - 1, 3, -1):  # From failed_step-1 down to 4
            if step in [4, 5]:
                compensation_steps.append(step)
        return compensation_steps
    
    _step_names = {
        1: SagaStep.VALIDAR_DATOS,
        2: SagaStep.VALIDAR_USUARIO,
        3: SagaStep.VALIDAR_EVENTO,
        4: SagaStep.PROCESAR_PAGO,
        5: SagaStep.CONFIRMAR_RESERVA,
        6: SagaStep.AUDITAR,
    }


# Compensation handlers
async def compensate_step_4_payment(context: ReservaContext) -> None:
    """Compensation for step 4: Lua script handles internal rollback."""
    # The Lua script handles internal rollback atomically
    # No additional action needed - just log
    logger.info(
        "Step 4 compensation: Lua atomic rollback executed",
        extra={"correlation_id": str(context.correlation_id)}
    )


async def compensate_step_5_reservation(context: ReservaContext) -> None:
    """Compensation for step 5: INCRBY inventory + DEL payment in Redis."""
    if not context.evento_id or not context.reserva_id:
        logger.warning("Missing evento_id or reserva_id for compensation")
        return
    
    from src.services.redis_pago import ejecutar_compensar_pago_inventario
    
    result = await ejecutar_compensar_pago_inventario(
        evento_id=str(context.evento_id),
        reserva_id=str(context.reserva_id),
        cantidad=context.cantidad
    )
    
    if result["success"]:
        logger.info(
            f"Step 5 compensation executed: INCRBY inventory + DEL pago for reserva {context.reserva_id}",
            extra={"correlation_id": str(context.correlation_id)}
        )
    else:
        logger.error(
            f"Step 5 compensation failed: {result['message']}",
            extra={"correlation_id": str(context.correlation_id)}
        )