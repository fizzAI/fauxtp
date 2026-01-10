# Troubleshooting

This document lists common failure modes when using `fauxtp`, how to diagnose them, and what to do about them.

Related docs:
- Runtime model: [`docs/actors.md`](docs/actors.md)
- Messaging: [`docs/messaging.md`](docs/messaging.md)
- Supervision: [`docs/supervision.md`](docs/supervision.md)

## “Nothing happens” (no output, no messages processed)

### 1) You didn’t start the actor in a TaskGroup
Actors must be started with `task_group=...` via [`python.Actor.start()`](src/fauxtp/actor/base.py:137).

If you do not keep the TaskGroup alive, the actor task is cancelled immediately.

Correct pattern:

```python
import anyio
from fauxtp import GenServer

class S(GenServer):
    async def init(self):
        print("started")
        return {}
    async def handle_call(self, req, _from, st):
        return "ok", st

async def main():
    async with anyio.create_task_group() as tg:
        pid = await S.start(task_group=tg)
        # keep task group alive while interacting
        ...
        tg.cancel_scope.cancel()

anyio.run(main)
```

### 2) You cancelled the TaskGroup too early
If your program ends or you call `tg.cancel_scope.cancel()`, children are cancelled too.

### 3) You sent a message but your actor never receives it
Double-check you’re using the right PID and the right message shape.

For GenServers, `call` and `cast` wrap your request:

- `cast(pid, request)` sends `("$cast", request)` ([`python.cast()`](src/fauxtp/messaging.py:18))
- `call(pid, request)` sends `("$call", ref, reply_to, request)` ([`python.call()`](src/fauxtp/messaging.py:25))

If you’re using a custom `Actor` (not `GenServer`) and expecting `("$cast", ...)`, you must implement matching receives yourself.

## `ReceiveTimeout` from `call()` or mailbox receive

### What it means
A timeout is raised by [`python.Mailbox.receive()`](src/fauxtp/primitives/mailbox.py:28) as [`python.ReceiveTimeout`](src/fauxtp/primitives/mailbox.py:85) when no *matching* message arrives before the deadline.

For `call()`, it usually means:

- the target process didn’t reply
- the reply message didn’t match the expected ref
- the target process died before replying
- the system is overloaded and didn’t schedule in time

### How to debug
- Increase timeout to see if it’s just slow scheduling.
- Confirm the target PID is correct (log it).
- Add logging in the server’s [`python.GenServer.handle_call()`](src/fauxtp/actor/genserver.py:57) to confirm the request arrives.
- Ensure you always return `(reply, new_state)` from `handle_call`.

## “My GenServer call returns None” (or unexpected replies)

Common causes:

- Your `match` patterns in `handle_call` fall through to the default case.
- You returned `(None, state)` intentionally but forgot to handle it on the caller side.
- You mutated and returned state inconsistently.

Recommendation: keep `handle_call` explicit and include an `else` branch that logs unknown requests.

## Supervisor doesn’t restart (or restarts unexpectedly)

### 1) RestartType rules
Child restart behavior depends on [`python.RestartType`](src/fauxtp/supervisor/child_spec.py:18):

- `PERMANENT`: restart always
- `TRANSIENT`: restart only on “abnormal exit”
- `TEMPORARY`: never restart

“Abnormal exit” is currently determined by string matching (`"error"` in the exit reason) inside [`python.Supervisor._handle_down()`](src/fauxtp/supervisor/base.py:121). If you want more precise control, use `PERMANENT` or extend the runtime to carry structured exit reasons.

### 2) Restart storm protection
If restarts happen too frequently, the supervisor raises [`python.MaxRestartsExceeded`](src/fauxtp/supervisor/base.py:21).

Tune:
- [`python.Supervisor.max_restarts`](src/fauxtp/supervisor/base.py:31)
- [`python.Supervisor.max_seconds`](src/fauxtp/supervisor/base.py:32)

### 3) Stale child-down messages
Supervisors include the exiting PID in the down message:

`("$child_down", child_id, pid, reason)`

This prevents old instances from triggering restarts after a replacement has already started.

If you change message shapes in your own code, keep this property.

## Registry lookups return None

### What it means
[`python.whereis()`](src/fauxtp/registry/local.py:72) returns `None` if the name isn’t registered.

### Common causes
- The actor never called [`python.register()`](src/fauxtp/registry/local.py:62) (or registration failed).
- You looked up the name before the actor finished `init()`.
- The name was already taken and `register()` returned `False`.

### How to debug
- Check the boolean return value of `register()` and log failures.
- Sleep briefly after starting a supervision tree (examples use small sleeps).
- Use [`python.registered()`](src/fauxtp/registry/local.py:77) to list names during debugging.

## Performance issues / high CPU

Selective receive works by scanning a deque:

- `Mailbox.receive()` iterates through buffered messages and patterns ([`python.Mailbox.receive()`](src/fauxtp/primitives/mailbox.py:28))

If you accumulate large mailboxes, you can get O(N) scans on every receive.

Mitigations:
- Keep queues short (backpressure at the application level).
- Use more specific patterns earlier.
- Design protocols so actors don’t ignore large classes of messages.
- Split responsibilities across multiple actors.

## Type checker warnings (basedpyright)

If you see complaints about `PID` or forward references, check:
- [`src/fauxtp/primitives/pid.py`](src/fauxtp/primitives/pid.py:1) uses `TYPE_CHECKING` imports so the mailbox type can be resolved.

If you add new forward references, prefer:
- `from __future__ import annotations`
- `if TYPE_CHECKING: ...` imports
