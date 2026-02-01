from typing_extensions import override
from .actor.genserver import GenServer
from .fauxstorage import FauxStorage, DEFAULT_FAUXSTORAGE
from .primitives.pid import PID, Ref

from typing import Any, TypeAlias

Request: TypeAlias = Any
State: TypeAlias = FauxStorage[str, PID]

class Registry(GenServer[Request, State]):
    @override
    async def init(self) -> State:
        return DEFAULT_FAUXSTORAGE[str, PID]()  # pyright: ignore[reportArgumentType]

    @override
    async def handle_call(self, request: Request, from_ref: Ref, state: State) -> tuple[Any, State]:
        match request:
            # Read
            case ("get", name):
                try:
                    return state.get(name), state
                except KeyError:
                    return None, state
            case _:
                return None, state

    @override
    async def handle_cast(self, request: Request, state: State) -> State:
        match request:
            case ("register", name, pid):
                state = state.set(name, pid)

            # Backwards-compat with earlier internal message name
            case ("unregister", name):
                if name in state:
                    state = state.delete(name)

        return state