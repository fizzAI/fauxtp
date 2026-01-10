# GenServer

`GenServer` (“generic server”) is an OTP-inspired abstraction for stateful actors with a conventional API:

- synchronous request/reply: `call`
- asynchronous fire-and-forget: `cast`
- everything else: `info`

Implementation: [`src/fauxtp/actor/genserver.py`](src/fauxtp/actor/genserver.py)

Related docs:
- Messaging API: [`docs/messaging.md`](docs/messaging.md)
- Actor lifecycle: [`docs/actors.md`](docs/actors.md)

## When to use GenServer

Use `GenServer` when:

- you want a single owner for mutable state
- callers need request/reply behavior
- you want structured message dispatch rather than writing your own receive loop

Examples include counters, caches, job queues, brokers, registries, coordinators.

## How GenServer works

[`python.GenServer`](src/fauxtp/actor/genserver.py:15) is a subclass of [`python.Actor`](src/fauxtp/actor/base.py:23).

Its [`python.GenServer.run()`](src/fauxtp/actor/genserver.py:25) does a single mailbox receive and dispatches based on message shape:

- `("$call", ref, from_pid, request)` → `_do_call()` → `handle_call()`
- `("$cast", request)` → `_do_cast()` → `handle_cast()`
- anything else → `_do_info()` → `handle_info()`

The key design is that your handler methods are about *business logic*, not mailbox mechanics.

## Required/optional handler methods

### `init()`

Optional override inherited from [`python.Actor.init()`](src/fauxtp/actor/base.py:52).

Return initial state (often a dict):

```python
class MyServer(GenServer):
    async def init(self):
        return {"value": 0}
```

### `handle_call(request, from_ref, state) -> (reply, new_state)`

Override [`python.GenServer.handle_call()`](src/fauxtp/actor/genserver.py:57) for synchronous requests.

Important:
- Return a `(reply, new_state)` tuple.
- `from_ref` is currently a correlation ref (not a process pid).

Example:

```python
class Counter(GenServer):
    async def handle_call(self, request, _from_ref, state):
        match request:
            case "get":
                return state["count"], state
            case ("add", n):
                new = state["count"] + n
                return new, {**state, "count": new}
        return None, state
```

### `handle_cast(request, state) -> new_state`

Override [`python.GenServer.handle_cast()`](src/fauxtp/actor/genserver.py:64) for async requests.

Default: returns the state unchanged.

```python
class Counter(GenServer):
    async def handle_cast(self, request, state):
        match request:
            case "reset":
                return {**state, "count": 0}
        return state
```

### `handle_info(message, state) -> new_state`

Override [`python.GenServer.handle_info()`](src/fauxtp/actor/genserver.py:72) for any message not matching call/cast.

Default: returns the state unchanged.

This gives you a “back door” to extend protocols without using `$call`/`$cast`.

## Using `call` / `cast` with a GenServer

To interact with a GenServer process, you generally use the messaging functions:

- [`python.call()`](src/fauxtp/messaging.py:25)
- [`python.cast()`](src/fauxtp/messaging.py:18)

Example:

```python
import anyio
from fauxtp import GenServer, call, cast

class Counter(GenServer):
    async def init(self): return {"count": 0}
    async def handle_call(self, request, _from_ref, state):
        match request:
            case "get": return state["count"], state
            case ("add", n):
                new = state["count"] + n
                return new, {**state, "count": new}
        return None, state
    async def handle_cast(self, request, state):
        if request == "reset":
            return {**state, "count": 0}
        return state

async def main():
    async with anyio.create_task_group() as tg:
        pid = await Counter.start(task_group=tg)
        await cast(pid, ("add", 1))          # note: cast does not return anything
        print(await call(pid, "get"))        # 0 (cast hasn't changed state unless you implement it)
        print(await call(pid, ("add", 10)))  # 10

        tg.cancel_scope.cancel()

anyio.run(main)
```

(That example demonstrates an important point: only `handle_cast` affects state for cast messages; calling `cast(pid, ("add", 1))` won’t do anything unless you implement it.)

## Error handling semantics

- Exceptions raised inside your handler methods are treated as actor failures.
- In supervision contexts, failures are surfaced via the supervisor’s “child down” messages and restart policy (see [`docs/supervision.md`](docs/supervision.md)).

## Practical patterns

### “Server-as-owner” pattern

Put all mutation inside the GenServer and only expose operations via call/cast. This keeps races out of your application logic.

### Timeouts

`call()` takes a timeout and will raise [`python.ReceiveTimeout`](src/fauxtp/primitives/mailbox.py:85) if no reply is received in time.

Use timeouts to avoid deadlocks and keep systems responsive.

### Avoid blocking in handlers

If a handler has to do slow work, either:
- await it directly (if it’s async I/O), or
- offload CPU work to threads/processes (AnyIO offers helpers), or
- implement a pipeline with multiple actors (see examples).
