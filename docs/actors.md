# Actors

This doc covers:

- What an actor is in `fauxtp`
- Lifecycle: `init()` → `run()` loop → `terminate()`
- Starting actors with structured concurrency
- Receiving messages and selective receive patterns
- Cancellation and failure behavior

The implementation lives in [`src/fauxtp/actor/base.py`](src/fauxtp/actor/base.py).

## What is an actor?

An actor is an object whose behavior is driven by messages delivered to its mailbox. Each running actor has:

- a mailbox: [`python.Mailbox`](src/fauxtp/primitives/mailbox.py:10)
- an address: [`python.PID`](src/fauxtp/primitives/pid.py:8)
- a task running an infinite loop implemented by your actor code: [`python.Actor.run()`](src/fauxtp/actor/base.py:56)

## Lifecycle

### `init()`

Override [`python.Actor.init()`](src/fauxtp/actor/base.py:52) to return initial state.

```python
from fauxtp import Actor

class MyActor(Actor):
    async def init(self):
        return {"count": 0}
```

### `run(state)`

Override [`python.Actor.run()`](src/fauxtp/actor/base.py:56) to implement “one iteration” of your actor loop.

Important: you normally write `run()` so it **awaits** a receive and returns updated state, so the runtime can keep calling it.

```python
from fauxtp import Actor, ANY

class MyActor(Actor):
    async def init(self):
        return {"messages": []}

    async def run(self, state):
        msg = await self.receive((ANY, lambda m: m))
        return {**state, "messages": state["messages"] + [msg]}
```

### `terminate(reason, state)`

Override [`python.Actor.terminate()`](src/fauxtp/actor/base.py:67) for cleanup/logging.

- It is invoked on error paths and on cancellation/normal exit where possible.
- `state` may be `None` if failure happens before `init()` completes.

## Starting actors (structured concurrency)

### `start(task_group=...) -> PID`

Use [`python.Actor.start()`](src/fauxtp/actor/base.py:137) to start an actor inside an AnyIO `TaskGroup`.

```python
import anyio
from fauxtp import Actor

class Worker(Actor):
    async def run(self, state):
        ...

async def main():
    async with anyio.create_task_group() as tg:
        pid = await Worker.start(task_group=tg)
        ...
        tg.cancel_scope.cancel()

anyio.run(main)
```

`fauxtp` intentionally requires a TaskGroup to avoid “floating background tasks”.

### `start_link(...)-> ActorHandle` (supervision / cancellation)

Use [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68) when you want a cancellation handle (supervisors use this).

It returns an [`python.ActorHandle`](src/fauxtp/actor/base.py:17) containing:

- `pid`: the actor’s [`python.PID`](src/fauxtp/primitives/pid.py:8)
- `cancel_scope`: an [`anyio.CancelScope`](src/fauxtp/actor/base.py:103) you can cancel to stop the actor task

## Receiving messages

### `Actor.receive()`

Actors receive from their own mailbox using [`python.Actor.receive()`](src/fauxtp/actor/base.py:44), which forwards to [`python.Mailbox.receive()`](src/fauxtp/primitives/mailbox.py:28).

A receive call takes a sequence of `(matcher, handler)` pairs:

```python
msg = await self.receive(
    (("tag", ANY), lambda value: ("tag", value)),
    (ANY, lambda m: ("other", m)),
)
```

### Pattern matching primitives

Matchers are processed by [`python.match_pattern()`](src/fauxtp/primitives/pattern.py:22). You can match:

- `ANY`: matches anything and extracts it ([`python.ANY`](src/fauxtp/primitives/pattern.py:11))
- `IGNORE` / `_`: matches anything and extracts nothing ([`python.IGNORE`](src/fauxtp/primitives/pattern.py:19))
- types: `str`, `int`, etc
- literal values: `"ping"`, `42`
- tuple structures: `("tag", ANY, str)`

Handlers receive extracted values:

- `ANY` extracts the matched value
- `IGNORE` extracts nothing
- type matches extract the value
- tuple matches extract values from inner matchers

Examples:

```python
from fauxtp import ANY, IGNORE

# ("ping", ANY) extracts the second element.
("ping", ANY)

# ("cmd", IGNORE, ANY) extracts only the last element.
("cmd", IGNORE, ANY)
```

## Cancellation and failures

### Cancellation

Actors run inside a cancel scope created in [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68). Cancelling it stops the actor task.

In supervisors, child cancellation is the mechanism used to “terminate” a child process.

### Exceptions in actors

The actor loop catches exceptions and reports an “exit reason” via the optional `on_exit` callback passed to [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68).

Supervisors use this to translate child exits into `"$child_down"` messages (see [`docs/supervision.md`](docs/supervision.md)).

Design intent:

- child failures should not implicitly crash the parent TaskGroup
- restart policy is handled by supervision logic rather than “exception bubbles”

## Tips for writing good actors

- Make `run()` do exactly one receive/dispatch iteration.
- Keep messages small and explicit (use tagged tuples).
- Put slow work behind awaits; avoid long CPU loops.
- Prefer `GenServer` for state machines where call/cast makes sense (see [`docs/genserver.md`](docs/genserver.md)).
