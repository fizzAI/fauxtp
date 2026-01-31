from dataclasses import dataclass
from typing_extensions import override

from .primitives.pid import PID
from .messaging import call, cast
from .registry import Registry
from .actor.base import Actor
from .fauxstorage.dict import DictFauxStorage

from enum import Enum
from typing import Any, TypeAlias

State: TypeAlias = DictFauxStorage[Any,Any]

class RestartStrategy(Enum):
    ONE_FOR_ONE = 1
    ONE_FOR_ALL = 2

@dataclass
class ChildSpec:
    actor: type[Actor]
    name: str
    args: tuple[Any,...] | None

class Supervisor(Actor):
    @override
    def __init__(self, children: list[ChildSpec], strategy: RestartStrategy, registry: PID | None = None):
        super().__init__()
        self.childspecs = children
        self.strategy = strategy
        self.registry = registry

    @override
    async def init(self) -> State:
        if not self.registry:
            # Q: should we use our parent or child tg here?
            self.registry = await Registry.start(task_group=self._children_tg)  # pyright: ignore[reportArgumentType]

        # NOTE: we need *specifically* the dict version here because we need to do a lot of fucky things with the dict that the real data structure doesnt support
        s: State = DictFauxStorage()
        return s.set("initialized", False)

    @override
    async def run(self, state: State) -> State:
        if not state.get("initialized"):
            for childspec in self.childspecs:
                async def on_exit():
                    pass
                if childspec.args:
                    _ = await self.spawn_child_actor(childspec.actor, *childspec.args, on_exit=on_exit)
                else:
                    _ = await self.spawn_child_actor(childspec.actor, on_exit=on_exit)
        else:
            pass
        return state