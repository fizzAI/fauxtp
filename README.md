# fauxtp

Erlang/OTP primitives for Python.

It brings `GenServer`, `Supervisor`, and pattern-matched message passing to Python's async ecosystem (via `anyio`).

It is not fast. It is not the BEAM. It is, however, a way to write concurrent Python that doesn't make you want to quit programming.

## Creation

**Most of this project was initially vibecoded.** However at this point I've had to put my grubby little mitts on it enough that I'm pretty confident that what it's doing is correct, and if it isn't then it's my fault too.

## Install

```bash
uv add fauxtp
```

## The Gist

> Note: actors are started **inside an AnyIO TaskGroup** (structured concurrency).
> You must pass `task_group=...` to [`python.Actor.start()`](src/fauxtp/actor/base.py#L137).

### GenServer

If you know OTP, you know this. If you don't: it's a stateful actor that handles synchronous `call`s and asynchronous `cast`s.

```python
from fauxtp import GenServer, call, cast
import anyio

class Counter(GenServer):
    async def init(self):
        return {"count": 0}

    async def handle_call(self, request, _from, state):
        match request:
            case "get":
                return state["count"], state
            case ("add", n):
                new_count = state["count"] + n
                return new_count, {"count": new_count}

    async def handle_cast(self, request, state):
        match request:
            case "reset":
                return {"count": 0}

async def main():
    async with anyio.create_task_group() as tg:
        pid = await Counter.start(task_group=tg)

        print(await call(pid, ("add", 5)))  # 5
        await cast(pid, "reset")
        print(await call(pid, "get"))       # 0

anyio.run(main)
```

### Supervisors

Let it crash. The supervisor restarts it.

```python
from fauxtp import Supervisor, ChildSpec, RestartStrategy

class App(Supervisor):
    strategy = RestartStrategy.ONE_FOR_ONE

    def child_specs(self):
        return [
            ChildSpec(id="c1", actor_class=Counter),
            ChildSpec(id="c2", actor_class=Counter),
        ]
```

## What's inside?

*   **Actors**: `send`, `receive` (with pattern matching).
*   **GenServer**: `call`, `cast`, `info`.
*   **Supervisors**: `one_for_one`, `one_for_all`, `rest_for_one`.
*   **Registry**: `register(name, pid)`, `whereis(name)`.

## Why?

Async Python often devolves into a mess of unmanaged tasks and race conditions. OTP solved this decades ago with structured concurrency trees. We're just borrowing their homework.

## Recommendations for more Elixir-like Python

The `fauxtp` code only requires `anyio` as a dependency, and that will remain true. However, if you want to have even more Elixir shenanigans, we can make the following recommendations:

- Treat server state as a value.
  - Do not mutate the incoming state in-place, always return a new state.
  - While this isn't *required* (Python is pass by reference, so any mutated state should apply to the overall state), we make no guarantees as to whether or not things will break.

- Prefer forcibly immutable/persistent state containers.
  - Avoid Python stdlib mutable collections (`list`, `dict`, `set`, most `collections.*`), except for tuples (and other immutables).
  - Consider [`rpds-py`](https://pypi.org/project/rpds-py/) or [`pyrsistent`](https://pypi.org/project/pyrsistent/) for persistent vectors/maps/sets.

- Avoid using `typing.Any` in user code where possible.
  - While we have to use it internally to avoid exploding errors (and some of this may leak to the more publicly aimed APIs), we highly recommend using `Generic[T]` where needed, as our `GenServer` does to specify its request and state types.