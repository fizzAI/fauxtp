"""
GenServer - Generic Server pattern.

Provides structured request/reply (call) and fire-and-forget (cast).
"""

import functools
from typing import Any, Generic
from typing_extensions import override, TypeVar

from fauxtp.type_utils import MaybeAwaitableCallable

from .base import Actor
from .task import Task
from ..messaging import send
from ..primitives.pid import PID, Ref
from ..primitives.pattern import ANY


R = TypeVar('R', default=Any)
S = TypeVar('S', default=Any)


class GenServer(Actor, Generic[R,S]):
    """
    GenServer implementation.
    
    Instead of run(), implement:
      - handle_call(request, from_ref, state) → (reply, new_state)
      - handle_cast(request, state) → new_state
      - handle_info(message, state) → new_state
      - handle_task_end(pid, result, state) → new_state
    """
    
    @override
    async def run(self, state: S) -> S:
        """Main GenServer loop - dispatches to handle_* methods."""
        return await self.receive(
            # call: ($call, ref, from_pid, request)
            (("$call", Ref, PID, ANY),
              functools.partial(self._do_call, state=state)),
            
            # cast: ($cast, request)
            (("$cast", ANY),
              functools.partial(self._do_cast, state=state)),

            # task success: ($$success, pid, result)
            (("$task_success", PID, ANY),
              functools.partial(self._do_task_end, state=state, success=True)),

            # task failure: ($$failure, pid, error)
            (("$task_failure", PID, ANY),
              functools.partial(self._do_task_end, state=state, success=False)),
            
            # anything else is info
            (ANY,
              functools.partial(self._do_info, state=state)),
        )
    
    async def _do_call(self, ref: Ref, from_pid: PID, request: R, state: S) -> S:
        """Handle call request and send reply."""
        reply, new_state = await self.handle_call(request, ref, state)
        await send(from_pid, ("$reply", ref, reply))
        return new_state
    
    async def _do_cast(self, request: R, state: S) -> S:
        """Handle cast request."""
        return await self.handle_cast(request, state)
    
    async def _do_info(self, message: R, state: S) -> S:
        """Handle info message."""
        return await self.handle_info(message, state)

    async def _do_task_end(self, pid: PID, val: Any, state: S, success: bool) -> S:
        """Internal handler for task completion."""
        return await self.handle_task_end(pid, "success" if success else "failure", val, state)

    async def spawn_task(self, func: MaybeAwaitableCallable, *args: Any, **kwargs: Any) -> PID | None:
        """Spawn a new task managed by this GenServer."""

        # Wrap func to apply args/kwargs
        async def _wrapped():
            res = func(*args, **kwargs)
            if hasattr(res, "__await__"):
                return await res
            return res

        handle = await Task.start_link(
            task_group=self.children,
            func=_wrapped,
            notify_pid=self.pid,
            success_message_name="$task_success",
            failure_message_name="$task_failure"
        )
        return handle.pid
    
    # --- Override these ---
    
    async def handle_call(self, request: R, from_ref: Ref, state: S) -> tuple[R, S]:  # pyright: ignore[reportUnusedParameter]
        """
        Handle synchronous request. Returns (reply, new_state).
        
        Override this method to handle call requests.
        """
        raise NotImplementedError(f"{self.__class__.__name__}.handle_call/3 not implemented")
    
    async def handle_cast(self, request: R, state: S) -> S:  # pyright: ignore[reportUnusedParameter]
        """
        Handle async request. Returns new_state.
        
        Override this method to handle cast requests.
        """
        return state
    
    async def handle_info(self, message: R, state: S) -> S:  # pyright: ignore[reportUnusedParameter]
        """
        Handle other messages. Returns new_state.
        
        Override this method to handle info messages.
        """
        return state

    async def handle_task_end(self, child_pid: PID, status: str, result: R, state: S) -> S:  # pyright: ignore[reportUnusedParameter]
        """
        Handle task completion or failure.
        result is {"status": "ok"|"error", "value": res|err}
        """
        return state