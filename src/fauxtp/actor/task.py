"""
Task - generic actor wrapper that runs an asynchronous function and provides nice syntax sugar.

Does not provide any methods for passing messages to it, use an Actor if you need those.
Useful if you want to spin off long-running work without blocking a main actors mailbox.
"""
from typing import Any
from anyio.abc import TaskGroup
from typing_extensions import override

from .base import Actor, ActorHandle
from ..messaging import send
from ..primitives.pid import PID
from ..primitives.pattern import ANY

from ..type_utils import typed_lambda, MaybeAwaitableCallable

class TaskHandle:
    """
    Special wrapper around an ActorHandle that provides nice utility functions for dealing with Tasks.
    """

    _handle: ActorHandle

    def __init__(self, handle: ActorHandle):
        self._handle = handle

    @property
    def pid(self) -> PID:
        """PID of the underlying Task actor."""
        return self._handle.pid

    def cancel(self) -> None:
        """Cancel the underlying Task actor."""
        self._handle.cancel_scope.cancel()

    async def join(self) -> Any:
        """
        Wait for Task completion and return its value, or raise on failure.
        """
        pid = self._handle.pid

        def _raise(ex: BaseException) -> "Any":
            raise ex

        return await pid._mailbox.receive(  # pyright: ignore[reportPrivateUsage]
            (("$success", ANY), typed_lambda[Any](lambda res: res)),
            (("$failure", ANY), typed_lambda[str](lambda reason: _raise(RuntimeError(reason)))),
        )


class Task(Actor):
    def __init__(
        self,
        func: MaybeAwaitableCallable,
        notify_pid: PID | None = None,
        success_message_name: str = "$$success",
        failure_message_name: str = "$$failure"
    ):
        super().__init__()
        self._func: MaybeAwaitableCallable = func
        self._notify_pid: PID | None = notify_pid
        self._success_message_name: str = success_message_name
        self._failure_message_name: str = failure_message_name
        self._sent_notify: bool = False

    async def notify(self, type: str, val: Any):
        match type:
            case "success":
                await send(self.pid, ("$success", val))
                if self._notify_pid is not None:
                    await send(self._notify_pid, (self._success_message_name, self.pid, val))
            case "failure":
                await send(self.pid, ("$failure", val))
                if self._notify_pid is not None:
                    await send(self._notify_pid, (self._failure_message_name, self.pid, val))
            case _:
                return
        self._sent_notify = True

    @override
    async def run(self, state: Any) -> Any:
        try:
            res = await self._func()
            await self.notify("success", res)
            self.stop("normal")
        except Exception as e:
            await self.notify("failure", repr(e))
            self.stop("error")

    @override
    async def terminate(self, reason: str, state: Any) -> None:
        # If we were cancelled before run() could report, unblock join()
        if not self._sent_notify:
            self._sent_notify = True
            await self.notify("failure", reason)

    # Special Task functions
    @classmethod
    async def spawn(cls, func: MaybeAwaitableCallable, task_group: TaskGroup):
        handle = await cls.start_link(func, task_group=task_group)
        return TaskHandle(handle)
   
    @classmethod
    async def spawn_and_notify(
        cls,
        func: MaybeAwaitableCallable,
        task_group: TaskGroup,
        parent_pid: PID,
        success_message_name: str = "$$success",
        failure_message_name: str = "$$failure",
    ):
        handle = await cls.start_link(
            func,
            task_group=task_group,
            notify_pid=parent_pid,
            success_message_name=success_message_name,
            failure_message_name=failure_message_name,
        )
        return TaskHandle(handle) 
