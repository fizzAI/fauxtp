# Supervisor API

## Supervisor

[`fauxtp.supervisor.base.Supervisor`](src/fauxtp/supervisor/base.py:26)

Base supervisor class. Subclass and define `child_specs()` and `strategy`.

### Attributes

- `strategy: RestartStrategy`: The restart strategy to use (default: `ONE_FOR_ONE`).
- `max_restarts: int`: Maximum number of restarts allowed within `max_seconds` (default: 3).
- `max_seconds: float`: Time window for `max_restarts` (default: 5.0).

### Methods to Override

#### `def child_specs(self) -> list[ChildSpec]`
Override to define the list of children to be supervised.

### Methods

#### `def child(self, child_id: str) -> PID | None`
Get a child's PID by its unique ID.

---

## ChildSpec

[`fauxtp.supervisor.child_spec.ChildSpec`](src/fauxtp/supervisor/child_spec.py:26)

Specification for a supervised child actor.

### Attributes

- `id: str`: Unique identifier for this child.
- `actor_class: type[Actor]`: The Actor class to instantiate.
- `args: tuple[Any, ...]`: Positional arguments for the actor constructor.
- `kwargs: dict[str, Any]`: Keyword arguments for the actor constructor.
- `restart: RestartType`: Restart behavior for this child (default: `PERMANENT`).

---

## Enums

### RestartStrategy

[`fauxtp.supervisor.child_spec.RestartStrategy`](src/fauxtp/supervisor/child_spec.py:11)

- `ONE_FOR_ONE`: Only restart the failed child.
- `ONE_FOR_ALL`: Restart all children if one fails.
- `REST_FOR_ONE`: Restart the failed child and all children started after it.

### RestartType

[`fauxtp.supervisor.child_spec.RestartType`](src/fauxtp/supervisor/child_spec.py:18)

- `PERMANENT`: Always restart.
- `TRANSIENT`: Restart only on abnormal exit (reason contains "error").
- `TEMPORARY`: Never restart.