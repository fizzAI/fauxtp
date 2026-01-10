# Registry

The registry is a simple **local name → PID** mapping used for discovery.

Implementation: [`src/fauxtp/registry/local.py`](src/fauxtp/registry/local.py)

Exports:
- [`python.register()`](src/fauxtp/registry/local.py:62)
- [`python.unregister()`](src/fauxtp/registry/local.py:67)
- [`python.whereis()`](src/fauxtp/registry/local.py:72)
- [`python.registered()`](src/fauxtp/registry/local.py:77)
- [`python.Registry`](src/fauxtp/registry/local.py:8) (the underlying class)

## What problem it solves

In a system with many actors, you often want to find “the” process for a role:

- `"kvstore"`
- `"pipeline:producer"`
- `"metrics:collector"`

In OTP you might use registered processes or a global registry. Here, `fauxtp` provides a lightweight, local-only registry.

## API

### `register(name, pid) -> bool`

Signature: [`python.register()`](src/fauxtp/registry/local.py:62)

- Returns `True` if the name was free and registration succeeded
- Returns `False` if the name was already registered

Example:

```python
from fauxtp import register

register("kvstore", self.pid)
```

### `unregister(name) -> bool`

Signature: [`python.unregister()`](src/fauxtp/registry/local.py:67)

- Returns `True` if the name existed and was removed
- Returns `False` if there was nothing to remove

### `whereis(name) -> PID | None`

Signature: [`python.whereis()`](src/fauxtp/registry/local.py:72)

Returns the PID associated with `name`, or `None` if not present.

Example:

```python
from fauxtp import whereis, call

store = whereis("kvstore")
if store is not None:
    stats = await call(store, "stats")
```

### `registered() -> list[str]`

Signature: [`python.registered()`](src/fauxtp/registry/local.py:77)

Returns the list of currently registered names.

## Thread safety

The current implementation uses a `threading.Lock` in [`python.Registry`](src/fauxtp/registry/local.py:8), making access safe across threads. In practice, most usage will be from async tasks on one event loop, but locking makes the primitive robust.

## Important limitations

- Local-only: there is no concept of nodes/distribution.
- No automatic cleanup: if a process dies, its name remains registered unless you explicitly unregister it.
  - A common pattern is to register in `init()` and unregister in `terminate()` (or implement a monitor).

## Naming conventions

Use names that make collisions unlikely and intent clear:

- `component` for singletons: `"kvstore"`, `"broker"`
- `namespace:component` for groups: `"pipeline:producer"`, `"pipeline:consumer"`
- `namespace:component:instance` for shards: `"pipeline:processor:1"`

This pattern is used in the examples:
- [`examples/01_concurrent_kvstore.py`](examples/01_concurrent_kvstore.py:1)
- [`examples/02_pipeline_processing.py`](examples/02_pipeline_processing.py:1)
