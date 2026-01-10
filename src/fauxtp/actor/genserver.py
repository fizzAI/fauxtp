"""
GenServer - Generic Server pattern.

Provides structured request/reply (call) and fire-and-forget (cast).
"""

from typing import Any

from .base import Actor
from ..messaging import send
from ..primitives.pid import PID, Ref
from ..primitives.pattern import ANY


class GenServer(Actor):
    """
    GenServer implementation.
    
    Instead of run(), implement:
      - handle_call(request, from_ref, state) → (reply, new_state)
      - handle_cast(request, state) → new_state
      - handle_info(message, state) → new_state
    """
    
    async def run(self, state: Any) -> Any:
        """Main GenServer loop - dispatches to handle_* methods."""
        return await self.receive(
            # call: ($call, ref, from_pid, request)
            ((("$call", Ref, PID, ANY), 
              lambda ref, from_pid, req: self._do_call(ref, from_pid, req, state))),
            
            # cast: ($cast, request)  
            ((("$cast", ANY),
              lambda req: self._do_cast(req, state))),
            
            # anything else is info
            ((ANY, 
              lambda msg: self._do_info(msg, state))),
        )
    
    async def _do_call(self, ref: Ref, from_pid: PID, request: Any, state: Any) -> Any:
        """Handle call request and send reply."""
        reply, new_state = await self.handle_call(request, ref, state)
        await send(from_pid, ("$reply", ref, reply))
        return new_state
    
    async def _do_cast(self, request: Any, state: Any) -> Any:
        """Handle cast request."""
        return await self.handle_cast(request, state)
    
    async def _do_info(self, message: Any, state: Any) -> Any:
        """Handle info message."""
        return await self.handle_info(message, state)
    
    # --- Override these ---
    
    async def handle_call(self, request: Any, from_ref: Ref, state: Any) -> tuple[Any, Any]:
        """
        Handle synchronous request. Returns (reply, new_state).
        
        Override this method to handle call requests.
        """
        raise NotImplementedError(f"{self.__class__.__name__}.handle_call/3 not implemented")
    
    async def handle_cast(self, request: Any, state: Any) -> Any:
        """
        Handle async request. Returns new_state.
        
        Override this method to handle cast requests.
        """
        return state
    
    async def handle_info(self, message: Any, state: Any) -> Any:
        """
        Handle other messages. Returns new_state.
        
        Override this method to handle info messages.
        """
        return state