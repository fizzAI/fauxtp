# Supervisors

Supervisors are actors that monitor other actors (children) and restart them if they crash. This is the core of the "Let it crash" philosophy.

## Child Specifications

A `ChildSpec` defines how a child actor should be started and managed.

```python
from fauxtp import ChildSpec

spec = ChildSpec(
    id="my_worker",
    actor_class=MyWorker,
    args=(1, 2, 3),
    restart="permanent" # or "temporary", "transient"
)
```

## Restart Strategies

- `ONE_FOR_ONE`: If a child process terminates, only that process is restarted.
- `ONE_FOR_ALL`: If a child process terminates, all other child processes are terminated, and then all child processes (including the terminated one) are restarted.
- `REST_FOR_ONE`: If a child process terminates, the rest of the child processes (those started after the terminated one) are terminated, and then the terminated process and the rest are restarted.

## Implementation

```python
from fauxtp import Supervisor, RestartStrategy

class MySupervisor(Supervisor):
    strategy = RestartStrategy.ONE_FOR_ONE

    def child_specs(self):
        return [
            ChildSpec(id="worker1", actor_class=Worker),
            ChildSpec(id="worker2", actor_class=Worker),
        ]
```

## Supervision Trees

Supervisors can supervise other supervisors, allowing you to build complex, hierarchical fault-tolerant systems.