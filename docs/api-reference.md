# API reference

This is a “practical reference” for the public API surface. It focuses on:

- what to import
- how to start processes
- how to message them
- how supervision + registry fit in

For deeper explanations, see:
- [`docs/getting-started.md`](docs/getting-started.md)
- [`docs/actors.md`](docs/actors.md)
- [`docs/messaging.md`](docs/messaging.md)
- [`docs/genserver.md`](docs/genserver.md)
- [`docs/supervision.md`](docs/supervision.md)
- [`docs/primitives.md`](docs/primitives.md)
- [`docs/registry.md`](docs/registry.md)

## Imports / public exports

The canonical entry point is [`src/fauxtp/__init__.py`](src/fauxtp/__init__.py:1).

Typical usage:

```python
from fauxtp import (
    Actor, GenServer, Supervisor,
    PID, Ref,
    Mailbox, ReceiveTimeout,
    ANY, IGNORE,
    send, cast, call,
    ChildSpec, RestartType, RestartStrategy, MaxRestartsExceeded,
    register, unregister, whereis, registered,
)
```

## Core primitives

### `PID`

Type: [`python.class PID`](src/fauxtp/primitives/pid.py:12)

Represents a process address. You generally do not construct PIDs manually (except internal patterns like reply-to), and you should not access internal fields.

### `Ref`

Type: [`python.class Ref`](src/fauxtp/primitives/pid.py:26)

A unique correlation reference, primarily used by [`python.call()`](src/fauxtp/messaging.py:25).

### `Mailbox`

Type: [`python.class Mailbox`](src/fauxtp/primitives/mailbox.py:10)

Low-level mailbox implementation. Most users won’t instantiate mailboxes directly unless doing advanced patterns or tests.

### `ReceiveTimeout`

Exception: [`python.class ReceiveTimeout`](src/fauxtp/primitives/mailbox.py:85)

Raised when a mailbox receive times out (including `call()` timeouts).

### `ANY` and `IGNORE`

Patterns:
- [`python.ANY`](src/fauxtp/primitives/pattern.py:11): match-any, extract value
- [`python.IGNORE`](src/fauxtp/primitives/pattern.py:19): match-any, extract nothing

Used for mailbox receive pattern matching.

## Actor API

### `Actor`

Base class: [`python.class Actor`](src/fauxtp/actor/base.py:23)

Override:
- [`python.Actor.init()`](src/fauxtp/actor/base.py:52) → initial state
- [`python.Actor.run()`](src/fauxtp/actor/base.py:56) → one loop iteration
- [`python.Actor.terminate()`](src/fauxtp/actor/base.py:67) → cleanup

Start:
- [`python.Actor.start()`](src/fauxtp/actor/base.py:137) (requires `task_group=...`) → `PID`
- [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68) (requires `task_group=...`) → [`python.ActorHandle`](src/fauxtp/actor/base.py:17)

Receive:
- [`python.Actor.receive()`](src/fauxtp/actor/base.py:44) forwards to mailbox receive

### `ActorHandle`

Type: [`python.class ActorHandle`](src/fauxtp/actor/base.py:17)

Returned by `start_link`, includes:
- `pid: PID`
- `cancel_scope: anyio.CancelScope`

This is primarily used by supervisors (and advanced users).

## Messaging API

All messaging functions are implemented in [`src/fauxtp/messaging.py`](src/fauxtp/messaging.py).

### `send(target: PID, message: Any) -> None`

Function: [`python.send()`](src/fauxtp/messaging.py:13)

Deliver an arbitrary message to `target`.

### `cast(target: PID, request: Any) -> None`

Function: [`python.cast()`](src/fauxtp/messaging.py:18)

Sends a conventional GenServer “cast” message:

- `("$cast", request)`

### `call(target: PID, request: Any, timeout: float = 5.0) -> Any`

Function: [`python.call()`](src/fauxtp/messaging.py:25)

Sends a conventional GenServer “call” message:

- `("$call", ref, reply_to_pid, request)`

Waits for the reply message:

- `("$reply", ref, reply_value)`

Raises [`python.ReceiveTimeout`](src/fauxtp/primitives/mailbox.py:85) if no matching reply arrives before `timeout`.

## GenServer API

Type: [`python.class GenServer`](src/fauxtp/actor/genserver.py:15)

You typically override:

- [`python.GenServer.handle_call()`](src/fauxtp/actor/genserver.py:57) → `(reply, new_state)`
- [`python.GenServer.handle_cast()`](src/fauxtp/actor/genserver.py:64) → `new_state`
- [`python.GenServer.handle_info()`](src/fauxtp/actor/genserver.py:72) → `new_state`

Dispatch is done in [`python.GenServer.run()`](src/fauxtp/actor/genserver.py:25) by matching message shapes.

## Supervision API

Supervisor types live in:
- [`src/fauxtp/supervisor/base.py`](src/fauxtp/supervisor/base.py)
- [`src/fauxtp/supervisor/child_spec.py`](src/fauxtp/supervisor/child_spec.py)

### `ChildSpec`

Type: [`python.class ChildSpec`](src/fauxtp/supervisor/child_spec.py:25)

Fields:
- `id: str`
- `actor_class: type[Actor]`
- `args: tuple[Any, ...] = ()`
- `kwargs: dict[str, Any] = {}`
- `restart: RestartType = RestartType.PERMANENT`

### `RestartType`

Enum: [`python.class RestartType`](src/fauxtp/supervisor/child_spec.py:18)

- `PERMANENT`
- `TRANSIENT`
- `TEMPORARY`

### `RestartStrategy`

Enum: [`python.class RestartStrategy`](src/fauxtp/supervisor/child_spec.py:11)

- `ONE_FOR_ONE`
- `ONE_FOR_ALL`
- `REST_FOR_ONE`

### `Supervisor`

Type: [`python.class Supervisor`](src/fauxtp/supervisor/base.py:25)

Override:
- [`python.Supervisor.child_specs()`](src/fauxtp/supervisor/base.py:34) to return `list[ChildSpec]`

Config:
- [`python.Supervisor.strategy`](src/fauxtp/supervisor/base.py:30)
- [`python.Supervisor.max_restarts`](src/fauxtp/supervisor/base.py:31)
- [`python.Supervisor.max_seconds`](src/fauxtp/supervisor/base.py:32)

Errors:
- [`python.MaxRestartsExceeded`](src/fauxtp/supervisor/base.py:21)

Internal supervisor protocol messages handled by [`python.Supervisor.run()`](src/fauxtp/supervisor/base.py:52) include:
- `("$child_down", child_id, pid, reason)`
- `("$terminate_child", child_id)`
- `("$restart_child", child_id)`
- `("$which_children",)`
- `("$count_children",)`

## Registry API

Implementation: [`src/fauxtp/registry/local.py`](src/fauxtp/registry/local.py)

Functions:
- [`python.register()`](src/fauxtp/registry/local.py:62) → `bool`
- [`python.unregister()`](src/fauxtp/registry/local.py:67) → `bool`
- [`python.whereis()`](src/fauxtp/registry/local.py:72) → `PID | None`
- [`python.registered()`](src/fauxtp/registry/local.py:77) → `list[str]`

Class:
- [`python.Registry`](src/fauxtp/registry/local.py:8)

## Testing helpers

Testing utilities are in [`src/fauxtp/testing/helpers.py`](src/fauxtp/testing/helpers.py).

- [`python.with_timeout()`](src/fauxtp/testing/helpers.py:11)
- [`python.assert_receives()`](src/fauxtp/testing/helpers.py:21)
- [`python.wait_for()`](src/fauxtp/testing/helpers.py:33)
- [`python.TestActor`](src/fauxtp/testing/helpers.py:55)

See [`docs/testing.md`](docs/testing.md).
