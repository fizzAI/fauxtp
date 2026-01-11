from typing import Any, Literal, TypeAlias
import anyio
from typing_extensions import override

from fauxtp import GenServer, Ref, call, cast

Request: TypeAlias = tuple[Literal["pop"]] | tuple[Literal["push"], Any]

class Stack(GenServer[Request, list[str]]):
    @override
    async def init(self, elements: str = ""):
        return elements.split(',')

    @override
    async def handle_call(self, request: Request, from_ref: Ref, state: list[str]) -> tuple[Any, Any]:
        match request:
            case ("pop",):
                to_caller = state.pop(0)
                return (to_caller, state)
            case _:
                raise RuntimeError("Invalid request type!")
    
    @override
    async def handle_cast(self, request: Request, state: list[str]) -> Any:
        match request:
            case ("push", element):
                state.insert(0, element)
                return state
            case _:
                raise RuntimeError("Invalid request type!")

async def main():
    async with anyio.create_task_group() as tg:
        pid = await Stack.start(task_group=tg, elements="hello,world")

        popped = await call(pid, ("pop",))
        print(popped)
        # -> "hello"

        await cast(pid, ("push", "fauxtp"))

        popped = await call(pid, ("pop",))
        print(popped)
        # -> "fauxtp"

        tg.cancel_scope.cancel()

if __name__ == "__main__":
    anyio.run(main)