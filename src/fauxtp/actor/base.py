"""Base actor class with lifecycle management."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import anyio
from anyio.abc import TaskGroup
import uuid

from ..primitives.pid import PID
from ..primitives.mailbox import Mailbox


@dataclass(frozen=True, slots=True)
class ActorHandle:
    """Handle to a running actor task."""
    pid: PID
    cancel_scope: anyio.CancelScope

class ActorExit(BaseException):
    def __init__(self, reason: str = "normal"):
        super().__init__(reason)
        self.reason = reason

class Actor(ABC):
    """
    Base actor class. Subclass and implement run().

    Lifecycle:
        init() → run() loops → terminate()
    """

    def __init__(self):
        super().__init__()
        self._pid: PID | None = None
        self._mailbox: Mailbox | None = None
        self._state: Any = None
        self._task_group: TaskGroup | None = None
        self._cancel_scope: anyio.CancelScope | None = None

    @property
    def pid(self) -> PID:
        if self._pid is None:
            raise RuntimeError("Actor not started")
        return self._pid

    async def receive(self, *patterns, timeout=None):
        """Receive from this actor's mailbox."""
        if self._mailbox is None:
            raise RuntimeError("Actor not started")
        return await self._mailbox.receive(*patterns, timeout=timeout)

    # --- Lifecycle hooks (override these) ---

    async def init(self) -> Any:
        """Initialize actor state. Returns initial state."""
        return {}

    @abstractmethod
    async def run(self, state: Any) -> Any:
        """
        Main actor loop body. Called repeatedly.
        Should await receive() and handle messages.
        Returns new state.
        """
        ...

    async def terminate(self, reason: str, state: Any) -> None:
        """Cleanup when actor stops."""
        pass

    # --- Actor runtime (don't override) ---

    @classmethod
    async def start_link(
        cls,
        *args,
        task_group: TaskGroup,
        on_exit: Callable[[PID, str], Awaitable[None]] | None = None,
        **kwargs,
    ) -> ActorHandle:
        """
        Start this actor inside the given AnyIO TaskGroup.

        Returns an ActorHandle containing the PID and a CancelScope that can be used
        to stop the actor task.

        Notes:
        - This API intentionally requires a TaskGroup to enforce structured concurrency.
        - Actor exceptions are caught and reported via on_exit; they do not crash the
          parent TaskGroup (OTP-style "let it crash" with supervision).
        """
        actor = cls(*args, **kwargs)
        actor._task_group = task_group
        actor._mailbox = Mailbox()
        actor._pid = PID(_id=uuid.uuid4(), _mailbox=actor._mailbox)
        actor._cancel_scope = anyio.CancelScope()

        cancelled_exc = anyio.get_cancelled_exc_class()

        async def _actor_loop() -> None:
            """Main actor execution loop."""
            state: Any = None
            reason = "normal"
            with actor._cancel_scope:  # pyright: ignore[reportOptionalContextManager]
                try:
                    state = await actor.init()
                    actor._state = state
                    while True:
                        state = await actor.run(state)
                        actor._state = state

                except ActorExit as e:
                    reason = e.reason

                except cancelled_exc:
                    reason = "cancelled"

                except Exception as e:
                    reason = f"error: {e!r}"

                finally:
                    with anyio.CancelScope(shield=True):
                        try:
                            # Always run actor cleanup
                                await actor.terminate(reason, state)
                        finally:
                            pass
                        if on_exit is not None and actor._pid is not None:
                            # Best-effort exit notification; never crash the task group.
                            try:
                                    await on_exit(actor._pid, reason)
                            except Exception:
                                pass

        task_group.start_soon(_actor_loop)
        return ActorHandle(pid=actor._pid, cancel_scope=actor._cancel_scope)

    @classmethod
    async def start(cls, *args, task_group: TaskGroup, **kwargs) -> PID:
        """Start this actor inside the given AnyIO TaskGroup and return its PID."""
        handle = await cls.start_link(*args, task_group=task_group, **kwargs)
        return handle.pid

    def stop(self, reason: str = "normal"):
        """Manually exits the actor with a given reason."""
        raise ActorExit(reason)