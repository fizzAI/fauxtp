"""
GenServer - Generic Server pattern.

Provides structured request/reply (call) and fire-and-forget (cast).
"""

import functools
from typing import Any, Generic
from typing_extensions import override, TypeVar

from .base import Actor
from .task import Task, TaskHandle
from ..messaging import send
from ..primitives.pid import PID, Ref
from ..primitives.pattern import ANY

from ..type_utils import MaybeAwaitableCallable


R = TypeVar('R', default=Any)
S = TypeVar('S', default=Any)


class GenServer(Actor, Generic[R,S]):
    """
    GenServer implementation.
    
    Instead of run(), implement:
      - handle_call(request, from_ref, state) → (reply, new_state)
      - handle_cast(request, state) → new_state
      - handle_info(message, state) → new_state

    This GenServer also supports spawning long-running background work using
    [`GenServer.start_background_task()`](src/fauxtp/actor/genserver.py:1), powered by
    [`Task`](src/fauxtp/actor/task.py:43).
    
    """

    # Task completion messages sent by [`Task.spawn_and_notify()`](src/fauxtp/actor/task.py:96)
    TASK_SUCCESS: str = "$task_success"
    TASK_FAILURE: str = "$task_failure"

    def __init__(self):
        super().__init__()
        # Track spawned background Tasks so we can correlate completions to caller-owned Refs.
        self._task_refs: dict[PID, Ref] = {}
    
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

            # background task completion
            ((self.TASK_SUCCESS, PID, ANY),
              functools.partial(self._do_task_success, state=state)),
            ((self.TASK_FAILURE, PID, ANY),
              functools.partial(self._do_task_failure, state=state)),
             
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

    async def _do_task_success(self, task_pid: PID, result: Any, state: S) -> S:
        task_ref = self._task_refs.pop(task_pid, None)
        return await self.handle_task_success(task_ref, task_pid, result, state)

    async def _do_task_failure(self, task_pid: PID, reason: Any, state: S) -> S:
        task_ref = self._task_refs.pop(task_pid, None)
        return await self.handle_task_failure(task_ref, task_pid, reason, state)

    async def start_background_task(
        self,
        func: MaybeAwaitableCallable,
        *,
        task_ref: Ref | None = None,
    ) -> tuple[Ref, TaskHandle]:
        """
        Spawn a long-running [`Task`](src/fauxtp/actor/task.py:43) as a child of this GenServer.

        The Task runs concurrently (does not block the GenServer mailbox). When it completes,
        this GenServer will receive either:
          - (`TASK_SUCCESS`, task_pid, result)
          - (`TASK_FAILURE`, task_pid, reason)

        which are routed to [`GenServer.handle_task_success()`](src/fauxtp/actor/genserver.py:1)
        and [`GenServer.handle_task_failure()`](src/fauxtp/actor/genserver.py:1).
        """
        ref = task_ref or Ref()
        task = await Task.spawn_and_notify(
            func,
            task_group=self.children,
            parent_pid=self.pid,
            success_message_name=self.TASK_SUCCESS,
            failure_message_name=self.TASK_FAILURE,
        )
        self._task_refs[task.pid] = ref
        return ref, task
    
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

    async def handle_task_success(
        self,
        task_ref: Ref | None,
        task_pid: PID,
        result: Any,
        state: S,
    ) -> S:  # pyright: ignore[reportUnusedParameter]
        """Called when a background task started via [`start_background_task()`](src/fauxtp/actor/genserver.py:1) completes successfully."""
        return state

    async def handle_task_failure(
        self,
        task_ref: Ref | None,
        task_pid: PID,
        reason: Any,
        state: S,
    ) -> S:  # pyright: ignore[reportUnusedParameter]
        """Called when a background task started via [`start_background_task()`](src/fauxtp/actor/genserver.py:1) fails or is cancelled."""
        return state
