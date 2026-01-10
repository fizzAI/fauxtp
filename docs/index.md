# fauxtp documentation

`fauxtp` is an Erlang/OTP-inspired actor toolkit for Python async (built on `anyio`), providing:

- Actors with mailboxes + selective receive
- A `GenServer` abstraction for stateful request/reply and casts
- A `Supervisor` abstraction for structured lifecycles + restarts
- A simple local name registry

This docs set is intentionally “whole codebase” oriented: it covers how to *use* the library, and how the pieces are implemented so you can reason about behavior.

## Quick start (the minimum mental model)

- Actors run inside an **AnyIO TaskGroup**. Start them with [`python.Actor.start()`](src/fauxtp/actor/base.py:137).
- You interact with processes via a [`python.PID`](src/fauxtp/primitives/pid.py:8).
- Message passing is explicit:
  - async send: [`python.send()`](src/fauxtp/messaging.py:13)
  - async “fire and forget”: [`python.cast()`](src/fauxtp/messaging.py:18)
  - async request/reply: [`python.call()`](src/fauxtp/messaging.py:25)
- Supervision is done by subclassing [`python.Supervisor`](src/fauxtp/supervisor/base.py:25) and providing [`python.ChildSpec`](src/fauxtp/supervisor/child_spec.py:25) entries.

## Install / run (uv-first)

From the repository root:

```bash
uv sync
uv run pytest -q
uv run python examples/01_concurrent_kvstore.py
```

## Documentation map

### Using the library
- [`docs/getting-started.md`](docs/getting-started.md): install, runtime model, “first actor”, “first GenServer”
- [`docs/actors.md`](docs/actors.md): [`python.Actor`](src/fauxtp/actor/base.py:23), lifecycle, cancellation, selective receive
- [`docs/messaging.md`](docs/messaging.md): message conventions, `send`/`cast`/`call`
- [`docs/genserver.md`](docs/genserver.md): [`python.GenServer`](src/fauxtp/actor/genserver.py:15), call/cast/info, message shapes
- [`docs/supervision.md`](docs/supervision.md): [`python.Supervisor`](src/fauxtp/supervisor/base.py:25), strategies, restart limits, “let it crash”
- [`docs/registry.md`](docs/registry.md): local naming via [`python.register()`](src/fauxtp/registry/local.py:62) / [`python.whereis()`](src/fauxtp/registry/local.py:72)
- [`docs/examples.md`](docs/examples.md): what each example demonstrates and how it works

### Primitives and internals
- [`docs/primitives.md`](docs/primitives.md): [`python.PID`](src/fauxtp/primitives/pid.py:8), [`python.Ref`](src/fauxtp/primitives/pid.py:19), [`python.Mailbox`](src/fauxtp/primitives/mailbox.py:10), patterns
- [`docs/design-notes.md`](docs/design-notes.md): intentional tradeoffs, identity model, structured concurrency constraints

### Testing and troubleshooting
- [`docs/testing.md`](docs/testing.md): helpers in [`src/fauxtp/testing/helpers.py`](src/fauxtp/testing/helpers.py)
- [`docs/troubleshooting.md`](docs/troubleshooting.md): common pitfalls, timeouts, “nothing happens” debugging

## Public API entry points

The main exports live in [`src/fauxtp/__init__.py`](src/fauxtp/__init__.py:1). The real implementations are:

- Actors: [`src/fauxtp/actor/base.py`](src/fauxtp/actor/base.py)
- GenServer: [`src/fauxtp/actor/genserver.py`](src/fauxtp/actor/genserver.py)
- Supervision: [`src/fauxtp/supervisor/base.py`](src/fauxtp/supervisor/base.py), [`src/fauxtp/supervisor/child_spec.py`](src/fauxtp/supervisor/child_spec.py)
- Messaging: [`src/fauxtp/messaging.py`](src/fauxtp/messaging.py)
- Primitives: [`src/fauxtp/primitives/`](src/fauxtp/primitives/)
- Registry: [`src/fauxtp/registry/local.py`](src/fauxtp/registry/local.py)