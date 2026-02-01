# Supervisor API

The supervisor implementation lives in [`src/fauxtp/supervisor.py`](src/fauxtp/supervisor.py:1).

It provides a small, OTP-inspired supervisor that:

- starts a set of child actors once
- monitors them via `on_exit` callbacks
- restarts children only when they exit with an `"error: ..."` reason
- supports `ONE_FOR_ONE` and `ONE_FOR_ALL` restart strategies

## `RestartStrategy`

[`RestartStrategy`](src/fauxtp/supervisor.py:22)

- `ONE_FOR_ONE`: restart only the failed child
- `ONE_FOR_ALL`: cancel all remaining children, then restart the full set once all have exited

## `ChildSpec`

[`ChildSpec`](src/fauxtp/supervisor.py:28)

Fields:

- `actor: type[Actor]` – child actor class (see [`Actor`](src/fauxtp/actor/base.py:30))
- `name: str` – name used for bookkeeping and registry registration
- `args: tuple[Any, ...] | None` – positional args passed to the actor constructor

## `Supervisor`

[`Supervisor`](src/fauxtp/supervisor.py:34)

### Construction

`Supervisor(children, strategy=..., registry=...)` where:

- `children: list[ChildSpec]`
- `strategy: RestartStrategy` (default: `RestartStrategy.ONE_FOR_ONE`)
- `registry: PID | None` – registry pid to register child names into

If `registry` is `None`, the supervisor starts its own [`Registry`](src/fauxtp/registry.py:11) as a child actor.

### Restart semantics

The actor runtime reports exit reasons as:

- `"normal"`
- `"cancelled"`
- `"error: {exc!r}"`

The supervisor restarts only when the reason starts with `"error:"` (see [`Supervisor._should_restart()`](src/fauxtp/supervisor.py:93)).

### Example

```python
import anyio

from fauxtp.actor.genserver import GenServer
from fauxtp.messaging import call
from fauxtp.registry import Registry
from fauxtp.supervisor import ChildSpec, RestartStrategy, Supervisor


class Worker(GenServer):
    async def init(self):
        return 0

    async def handle_call(self, request, _from, state):
        return state, state


async def main():
    async with anyio.create_task_group() as tg:
        registry = await Registry.start(task_group=tg)

        _sup_pid = await Supervisor.start(
            children=[
                ChildSpec(actor=Worker, name="worker-1"),
                ChildSpec(actor=Worker, name="worker-2"),
            ],
            strategy=RestartStrategy.ONE_FOR_ONE,
            registry=registry,
            task_group=tg,
        )

        worker_1 = await call(registry, ("get", "worker-1"))
        assert worker_1 is not None


anyio.run(main)
```

Notes:

- Child `name`s are registered via `cast(registry, ("register", name, pid))` (see [`Registry.handle_cast()`](src/fauxtp/registry.py:29)).
- The supervisor is intentionally minimal; it currently supports only `ONE_FOR_ONE` and `ONE_FOR_ALL`, and uses a single restart rule (restart only on `"error: ..."` exits).