from __future__ import annotations

import functools
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

from typing_extensions import override

from .actor.base import Actor, ActorHandle
from .fauxstorage.dict import DictFauxStorage
from .messaging import cast, send
from .primitives.pattern import ANY
from .primitives.pid import PID
from .registry import Registry

State: TypeAlias = DictFauxStorage[Any, Any]

_CHILD_EXIT_MSG = "$supervisor_child_exit"


class RestartStrategy(Enum):
    ONE_FOR_ONE = 1
    ONE_FOR_ALL = 2


@dataclass(frozen=True, slots=True)
class ChildSpec:
    actor: type[Actor]
    name: str
    args: tuple[Any, ...] | None = None


class Supervisor(Actor):
    """
    Minimal supervisor.

    - Starts an internal [`src/fauxtp/registry.py:11`](src/fauxtp/registry.py:11) unless provided.
    - Spawns initial children once.
    - Monitors child exit via per-child `on_exit` callbacks.
    - Restarts on `"error: ..."` exits.
    """

    @override
    def __init__(
        self,
        children: list[ChildSpec],
        strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE,
        registry: PID | None = None,
    ):
        super().__init__()
        self.childspecs: list[ChildSpec] = children
        self.strategy: RestartStrategy = strategy
        self.registry: PID | None = registry

    @override
    async def init(self) -> State:
        if self.registry is None:
            # The registry is a child of the supervisor, so it is cancelled with the supervisor.
            self.registry = await Registry.start(task_group=self.children)

        # NOTE: we need *specifically* the dict version here because we need to do a lot
        # of state surgery that a stricter persistent DS doesn't support yet.
        s: State = DictFauxStorage()
        s = s.set("initialized", False)
        s = s.set("awaiting_all_exit", None)  # set[PID] | None
        s = s.set("specs_by_name", {})  # dict[str, ChildSpec]
        s = s.set("handles_by_name", {})  # dict[str, ActorHandle]
        s = s.set("pid_to_name", {})  # dict[PID, str]
        return s

    async def _register(self, name: str, pid: PID) -> None:
        if self.registry is None:
            return
        await cast(self.registry, ("register", name, pid))

    async def _unregister(self, name: str) -> None:
        if self.registry is None:
            return
        await cast(self.registry, ("unregister", name))

    async def _start_child(self, spec: ChildSpec) -> ActorHandle:
        async def _on_exit(child_pid: PID, reason: str) -> None:
            # Route child exits back through the supervisor mailbox so supervision
            # is processed serially.
            await send(self.pid, (_CHILD_EXIT_MSG, child_pid, reason))

        args = spec.args or ()
        handle = await self.spawn_child_actor(spec.actor, *args, on_exit=_on_exit)
        await self._register(spec.name, handle.pid)
        return handle

    def _should_restart(self, reason: str) -> bool:
        # Actor runtime uses:
        # - "normal"
        # - "cancelled"
        # - f"error: {exc!r}"
        return reason.startswith("error:")

    async def _handle_child_exit(self, child_pid: PID, reason: str, state: State) -> State:
        awaiting_all_exit: set[PID] | None = state.get("awaiting_all_exit")

        specs_by_name: dict[str, ChildSpec] = dict(state.get("specs_by_name"))
        handles_by_name: dict[str, ActorHandle] = dict(state.get("handles_by_name"))
        pid_to_name: dict[PID, str] = dict(state.get("pid_to_name"))

        # If we're in the middle of a ONE_FOR_ALL restart, we just wait for the
        # remaining children to exit, then start a clean slate.
        if awaiting_all_exit is not None:
            waiting = set(awaiting_all_exit)
            waiting.discard(child_pid)

            if len(waiting) == 0:
                # All previous children are down; start fresh.
                handles_by_name = {}
                pid_to_name = {}

                for spec in self.childspecs:
                    handle = await self._start_child(spec)
                    handles_by_name[spec.name] = handle
                    pid_to_name[handle.pid] = spec.name

                state = state.set("awaiting_all_exit", None)
                state = state.set("handles_by_name", handles_by_name)
                state = state.set("pid_to_name", pid_to_name)
                return state

            return state.set("awaiting_all_exit", waiting)

        # Normal supervision path
        name = pid_to_name.pop(child_pid, None)
        if name is None:
            # Unknown child (or already handled). Ignore.
            return state

        handles_by_name.pop(name, None)
        await self._unregister(name)

        # Remove it from state first (even if we restart) to avoid stale entries.
        state = state.set("handles_by_name", handles_by_name)
        state = state.set("pid_to_name", pid_to_name)

        if not self._should_restart(reason):
            return state

        match self.strategy:
            case RestartStrategy.ONE_FOR_ONE:
                spec = specs_by_name[name]
                handle = await self._start_child(spec)
                handles_by_name[name] = handle
                pid_to_name[handle.pid] = name
                state = state.set("handles_by_name", handles_by_name)
                state = state.set("pid_to_name", pid_to_name)
                return state

            case RestartStrategy.ONE_FOR_ALL:
                # Cancel all remaining children and wait for their exit callbacks.
                waiting_pids = set(pid_to_name.keys())

                # Unregister remaining children eagerly (so lookups don't point at soon-to-die pids).
                for child_name in list(handles_by_name.keys()):
                    await self._unregister(child_name)

                for handle in handles_by_name.values():
                    handle.cancel_scope.cancel()

                # If there are no remaining children, restart immediately.
                if len(waiting_pids) == 0:
                    handles_by_name = {}
                    pid_to_name = {}
                    for spec in self.childspecs:
                        handle = await self._start_child(spec)
                        handles_by_name[spec.name] = handle
                        pid_to_name[handle.pid] = spec.name
                    state = state.set("handles_by_name", handles_by_name)
                    state = state.set("pid_to_name", pid_to_name)
                    return state

                state = state.set("handles_by_name", {})
                state = state.set("pid_to_name", {})
                state = state.set("awaiting_all_exit", waiting_pids)
                return state

        return state

    @override
    async def run(self, state: State) -> State:
        if not state.get("initialized"):
            specs_by_name: dict[str, ChildSpec] = {spec.name: spec for spec in self.childspecs}
            handles_by_name: dict[str, ActorHandle] = {}
            pid_to_name: dict[PID, str] = {}

            for spec in self.childspecs:
                handle = await self._start_child(spec)
                handles_by_name[spec.name] = handle
                pid_to_name[handle.pid] = spec.name

            state = state.set("initialized", True)
            state = state.set("specs_by_name", specs_by_name)
            state = state.set("handles_by_name", handles_by_name)
            state = state.set("pid_to_name", pid_to_name)
            return state

        return await self.receive(
            ((_CHILD_EXIT_MSG, PID, str), functools.partial(self._handle_child_exit, state=state)),
            (ANY, lambda _msg: state),
        )

    @override
    async def terminate(self, reason: str, state: State) -> None:
        # Best-effort cleanup: unregister names so callers don't get stale pids.
        try:
            handles_by_name: dict[str, ActorHandle] = dict(state.get("handles_by_name"))
        except Exception:
            handles_by_name = {}

        for name in list(handles_by_name.keys()):
            try:
                await self._unregister(name)
            except Exception:
                pass