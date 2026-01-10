# Getting started

This guide walks through the “happy path” for using `fauxtp`:

- Start actors with structured concurrency (`anyio` TaskGroups)
- Send messages with `send` / `cast` / `call`
- Write a simple `GenServer`
- Run an example using `uv`

## Installation / running

From the repo root:

```bash
uv sync
uv run pytest -q
```

To run an example:

```bash
uv run python examples/01_concurrent_kvstore.py
```

## Core mental model

### Processes are tasks with mailboxes

A process in `fauxtp` is an async task that:

- owns a mailbox ([`python.Mailbox`](src/fauxtp/primitives/mailbox.py:10))
- runs an event loop implemented by your actor class ([`python.Actor`](src/fauxtp/actor/base.py:23))
- is addressed by a [`python.PID`](src/fauxtp/primitives/pid.py:8)

### You must start actors in an AnyIO TaskGroup

Actors are started with [`python.Actor.start()`](src/fauxtp/actor/base.py:137), which requires `task_group=...`.

This is intentional: it enforces structured concurrency so lifetimes and cancellation are explicit and supervisors can own their children’s tasks.

```python
import anyio
from fauxtp import Actor

class MyActor(Actor):
    async def run(self, state):
        ...
        return state

async def main():
    async with anyio.create_task_group() as tg:
        pid = await MyActor.start(task_group=tg)
        ...
        tg.cancel_scope.cancel()

anyio.run(main)
```

## Messaging API

Messaging is implemented in [`src/fauxtp/messaging.py`](src/fauxtp/messaging.py).

- [`python.send()`](src/fauxtp/messaging.py:13): send any message (no reply expected)
- [`python.cast()`](src/fauxtp/messaging.py:18): conventional “fire and forget” request message
- [`python.call()`](src/fauxtp/messaging.py:25): synchronous request/reply (with timeout)

A `call()` uses a unique [`python.Ref`](src/fauxtp/primitives/pid.py:19) to correlate a reply.

## Your first GenServer: a counter

`GenServer` is implemented in [`src/fauxtp/actor/genserver.py`](src/fauxtp/actor/genserver.py). You implement:

- [`python.GenServer.handle_call()`](src/fauxtp/actor/genserver.py:57) for request/reply
- [`python.GenServer.handle_cast()`](src/fauxtp/actor/genserver.py:64) for fire-and-forget
- [`python.GenServer.handle_info()`](src/fauxtp/actor/genserver.py:72) for “everything else”

Example:

```python
import anyio
from fauxtp import GenServer, call, cast

class Counter(GenServer):
    async def init(self):
        return {"count": 0}

    async def handle_call(self, request, _from_ref, state):
        match request:
            case "get":
                return state["count"], state
            case ("add", n):
                new = state["count"] + n
                return new, {**state, "count": new}
        return None, state

    async def handle_cast(self, request, state):
        match request:
            case "reset":
                return {**state, "count": 0}
        return state

async def main():
    async with anyio.create_task_group() as tg:
        pid = await Counter.start(task_group=tg)

        print(await call(pid, ("add", 5)))  # 5
        await cast(pid, "reset")
        print(await call(pid, "get"))       # 0

        tg.cancel_scope.cancel()

anyio.run(main)
```

## Where to go next

- Actors and lifecycle details: [`docs/actors.md`](docs/actors.md)
- Messaging conventions: [`docs/messaging.md`](docs/messaging.md)
- GenServer deep dive: [`docs/genserver.md`](docs/genserver.md)
- Supervision trees: [`docs/supervision.md`](docs/supervision.md)
- Primitives (mailbox/patterns): [`docs/primitives.md`](docs/primitives.md)