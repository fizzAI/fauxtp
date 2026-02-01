# Supervisors

A supervisor is an actor that starts other actors (children), watches them, and restarts them when they crash.

In fauxtp, the supervisor is implemented in [`src/fauxtp/supervisor.py`](src/fauxtp/supervisor.py:1) and is intentionally minimal:

- children are defined up front using [`ChildSpec`](src/fauxtp/supervisor.py:28)
- restart decisions are based on the child exit `reason` string emitted by the actor runtime:
  - `"normal"`, `"cancelled"`, or `"error: ..."` (see [`Actor.start_link()`](src/fauxtp/actor/base.py:96))
- only `"error: ..."` exits are restarted (see [`Supervisor._should_restart()`](src/fauxtp/supervisor.py:93))

## Child specifications

A [`ChildSpec`](src/fauxtp/supervisor.py:28) defines how to start a child actor.

```python
from fauxtp.supervisor import ChildSpec
from my_app.workers import Worker

spec = ChildSpec(
    actor=Worker,
    name="worker-1",
    args=(1, 2, 3),
)
```

Notes:

- `name` is used for supervisor bookkeeping and for registry registration (see “Registry integration” below).
- `args` are positional constructor arguments for the actor class.

## Restart strategies

Restart strategies are defined by [`RestartStrategy`](src/fauxtp/supervisor.py:22):

- `RestartStrategy.ONE_FOR_ONE`:
  - if a child crashes, restart only that child
- `RestartStrategy.ONE_FOR_ALL`:
  - if a child crashes, cancel all remaining children and restart the whole set once all have exited

## Starting a supervisor

The supervisor is itself an actor, so you start it the same way as any other actor: inside an AnyIO `TaskGroup` (structured concurrency).

```python
import anyio

from fauxtp.registry import Registry
from fauxtp.supervisor import Supervisor, ChildSpec, RestartStrategy
from my_app.workers import Worker


async def main():
    async with anyio.create_task_group() as tg:
        registry = await Registry.start(task_group=tg)

        _sup_pid = await Supervisor.start(
            children=[
                ChildSpec(actor=Worker, name="worker-1", args=(1,)),
                ChildSpec(actor=Worker, name="worker-2", args=(2,)),
            ],
            strategy=RestartStrategy.ONE_FOR_ONE,
            registry=registry,
            task_group=tg,
        )


anyio.run(main)
```

If you pass `registry=None`, the supervisor will start its own internal [`Registry`](src/fauxtp/registry.py:11) as a child actor (see [`Supervisor.init()`](src/fauxtp/supervisor.py:57)).

## Registry integration

When the supervisor starts a child, it registers that child's `name` into the registry:

- register: `cast(registry, ("register", name, pid))` (see [`Supervisor._register()`](src/fauxtp/supervisor.py:72))
- unregister: `cast(registry, ("unregister", name))` (see [`Supervisor._unregister()`](src/fauxtp/supervisor.py:77))

Callers can resolve a child PID with a `call`:

```python
from fauxtp.messaging import call

worker_1 = await call(registry, ("get", "worker-1"))
```

If the child is currently down (or was never registered), this returns `None` (see [`Registry.handle_call()`](src/fauxtp/registry.py:17)).

## Supervision trees

You can build supervision trees by supervising other supervisors, since [`Supervisor`](src/fauxtp/supervisor.py:34) is an [`Actor`](src/fauxtp/actor/base.py:30).

```python
import anyio

from fauxtp.registry import Registry
from fauxtp.supervisor import Supervisor, ChildSpec, RestartStrategy


async def main():
    async with anyio.create_task_group() as tg:
        registry = await Registry.start(task_group=tg)

        await Supervisor.start(
            children=[
                ChildSpec(
                    actor=Supervisor,
                    name="subtree",
                    args=(
                        [
                            ChildSpec(actor=SomeWorker, name="w1"),
                            ChildSpec(actor=SomeWorker, name="w2"),
                        ],
                        RestartStrategy.ONE_FOR_ONE,
                        registry,
                    ),
                ),
            ],
            strategy=RestartStrategy.ONE_FOR_ALL,
            registry=registry,
            task_group=tg,
        )


anyio.run(main)
```

Tip: passing the same registry PID down the tree lets you resolve names from a single place.

## What this supervisor does *not* do (yet)

This supervisor is intentionally small. It currently does not implement:

- a “restart only later siblings” strategy (i.e. anything beyond restarting just the crashed child, or restarting the whole set)
- per-child restart policies (all children use the same rule: restart only on `"error: ..."` exits)
- restart intensity limits / rate limiting
- a public “child lookup” API on the supervisor itself (use the registry if you need name → pid)