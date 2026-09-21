"""Chain of Responsibility base handler for Reservas Service."""
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime

# Import ReservaContext from models
from src.models.reserva import ReservaContext, SagaStep


class Handler(ABC):
    """Base abstract handler for Chain of Responsibility."""
    
    def __init__(self):
        self._next_handler: Optional["Handler"] = None
    
    def set_next(self, handler: "Handler") -> "Handler":
        """Set next handler in chain and return it for chaining."""
        self._next_handler = handler
        return handler
    
    @abstractmethod
    async def handle(self, context: ReservaContext) -> ReservaContext:
        """Handle the request and pass to next handler."""
        pass
    
    async def _execute_next(self, context: ReservaContext) -> ReservaContext:
        """Execute next handler in chain if exists."""
        if self._next_handler:
            return await self._next_handler.handle(context)
        return context
    
    def _add_saga_log(
        self, 
        context: ReservaContext, 
        step: str, 
        exitoso: bool, 
        detalles: Optional[str] = None
    ) -> None:
        """Add entry to saga_log."""
        import datetime
        entry = {
            "paso": step,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "exitoso": exitoso
        }
        if detalles:
            entry["detalles"] = detalles
        context.saga_log.append(entry)


class BaseHandler(Handler):
    """Base handler with common functionality."""
    
    def __init__(self):
        super().__init__()
        self._step_name: str = ""
    
    @property
    def step_name(self) -> str:
        return self._step_name
    
    @step_name.setter
    def step_name(self, value: str):
        self._step_name = value
    
    async def handle(self, context: ReservaContext) -> ReservaContext:
        """Main handle method - implements the chain."""
        # Check if chain should stop due to error
        if context.error or context.status_code >= 400:
            return context
        
        try:
            await self._process(context)
        except Exception as e:
            context.error = str(e)
            context.status_code = 500
            self._add_saga_log(context, self._step_name, False, str(e))
            return context
        
        # Check if _process set an error
        if context.error or context.status_code >= 400:
            return context
        
        # Continue to next handler
        return await self._execute_next(context)
    
    @abstractmethod
    async def _process(self, context: ReservaContext) -> None:
        """Process logic for this handler."""
        pass