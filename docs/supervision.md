# Supervision

Supervision is the OTP idea: **processes are expected to fail**, and supervisors own the responsibility for restarting them according to policy.

In `fauxtp`, supervisors are actors that:

- start child processes (actors) from a declarative child spec list
- receive “child down” notifications
- restart children according to a strategy and rate limits

Implementation: [`src/fauxtp/supervisor/base.py`](src/fauxtp/supervisor/base.py) and [`src/fauxtp/supervisor/child_spec.py`](src/fauxtp/supervisor/child_spec.py)

Related docs:
- Actors: [`docs/actors.md`](docs/actors.md)
- GenServer: [`docs/genserver.md`](docs/genserver.md)

## Core concepts

### ChildSpec

A child specification describes how to start a child actor.

See [`python.ChildSpec`](src/fauxtp/supervisor/child_spec.py:25).

Fields:

- `id`: stable identifier for the child within the supervisor
- `actor_class`: the class to instantiate (must have `.start_link`/`.start`)
- `args`, `kwargs`: constructor args/kwargs for the actor
- `restart`: restart policy (see below)

Example:

```python
from fauxtp import ChildSpec, RestartType
from myapp.workers import Worker

ChildSpec(
    id="worker1",
    actor_class=Worker,
    args=("name",),
    restart=RestartType.PERMANENT,
)
```

### RestartType (per child)

See [`python.RestartType`](src/fauxtp/supervisor/child_spec.py:18).

- `PERMANENT`: always restart
- `TRANSIENT`: restart only on abnormal exit
- `TEMPORARY`: never restart

Note: “abnormal exit” is currently based on the `reason` string provided by the actor runtime (see [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68)). `TRANSIENT` checks for `"error"` in the reason string.

### RestartStrategy (supervisor-wide)

See [`python.RestartStrategy`](src/fauxtp/supervisor/child_spec.py:11).

- `ONE_FOR_ONE`: restart only the failed child
- `ONE_FOR_ALL`: restart all children when any child fails
- `REST_FOR_ONE`: restart the failed child and all children started after it

## Supervisor runtime

### Subclassing Supervisor

You typically subclass [`python.Supervisor`](src/fauxtp/supervisor/base.py:25) and override `child_specs()`:

```python
from fauxtp import Supervisor, ChildSpec, RestartStrategy

class MyApp(Supervisor):
    strategy = RestartStrategy.ONE_FOR_ONE

    def child_specs(self):
        return [
            ChildSpec(id="worker1", actor_class=Worker),
            ChildSpec(id="worker2", actor_class=Worker),
        ]
```

### Starting children

On init, [`python.Supervisor.init()`](src/fauxtp/supervisor/base.py:38) starts all children and stores their runtime info in `state["children"]`.

A key requirement is that the supervisor itself must be started in a TaskGroup, because child tasks are started in the *supervisor’s* TaskGroup via [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68).

### Child exit detection

When a child task exits, the supervisor gets a mailbox message:

- `("$child_down", child_id, pid, reason)`

This is sent by the `on_exit` callback passed to the child’s [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68).

Including `pid` allows the supervisor to ignore “stale” exits (e.g., if a previous instance exits after a restart).

### Restart limits

The supervisor tracks restart timestamps in a deque:

- `max_restarts`: maximum restart events
- `max_seconds`: sliding time window

If too many restarts happen in the window, it raises [`python.MaxRestartsExceeded`](src/fauxtp/supervisor/base.py:21).

This matches the OTP idea of “don’t restart forever”.

## External supervisor commands

The supervisor’s [`python.Supervisor.run()`](src/fauxtp/supervisor/base.py:52) understands a small internal command set:

- `("$terminate_child", child_id)`
- `("$restart_child", child_id)`
- `("$which_children",)`
- `("$count_children",)`

At the moment, these commands are not wrapped by a public “supervisor API” module; you can send them via [`python.send()`](src/fauxtp/messaging.py:13) or add helper functions in your application.

## Design notes / current limitations

- There is no supervisor “PID -> child PID lookup” API yet. If you need discovery, use the registry (see [`docs/registry.md`](docs/registry.md)) or extend the supervisor protocol.
- The `TRANSIENT` restart decision uses a string heuristic (`"error"` in reason). This may evolve into a richer exit reason type.
- This is a “single-node” system: PIDs are local and there is no distribution/remote messaging.

## Practical patterns

### Register children in `init()`

For discoverability, children can register themselves by name during init:

```python
from fauxtp import GenServer, register

class Cache(GenServer):
    async def init(self):
        register("cache", self.pid)
        return {}
```

### Keep supervisors thin

In OTP, supervisors are intended to be declarative and boring. Put business logic in workers/servers; supervisors should orchestrate lifecycle.
