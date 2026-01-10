# Testing

This document covers how the project’s tests are structured and what helper utilities exist.

Tests live in `tests/`. Testing helpers live in [`src/fauxtp/testing/helpers.py`](src/fauxtp/testing/helpers.py).

## Running tests

This repo is `uv`-oriented:

```bash
uv sync
uv run pytest -q
```

## Test layout

- Actor behavior: `tests/test_actor.py`
- GenServer behavior: `tests/test_genserver.py`
- Supervisor behavior: `tests/test_supervisor.py`
- Registry: `tests/test_registry.py`
- Primitives: `tests/test_primitives.py`
- Edge cases: `tests/test_edge_cases.py`
- Testing utilities: `tests/test_testing_helpers.py`

## Helper utilities

### `with_timeout(coro, timeout=...)`

Implementation: [`python.with_timeout()`](src/fauxtp/testing/helpers.py:11)

Wraps a coroutine with an AnyIO timeout:

- uses `anyio.fail_after(timeout)`
- re-raises an exception if the timeout expires

Example:

```python
from fauxtp.testing.helpers import with_timeout

result = await with_timeout(call(pid, "get"), timeout=1.0)
```

### `assert_receives(actor, *patterns, timeout=...)`

Implementation: [`python.assert_receives()`](src/fauxtp/testing/helpers.py:21)

Asserts that a running actor receives a message matching provided patterns within `timeout`.

This is mainly useful when you have an actual actor instance (not just a PID) and want to validate mailbox flows.

### `wait_for(condition, timeout=..., interval=...)`

Implementation: [`python.wait_for()`](src/fauxtp/testing/helpers.py:33)

Polls `condition()` until it returns `True`, sleeping `interval` between attempts, and raises `TimeoutError` if the deadline passes.

This is useful for eventual-consistency style assertions where you can’t or don’t want to add explicit acknowledgement messages.

### `TestActor`

Implementation: [`python.class TestActor`](src/fauxtp/testing/helpers.py:55)

A simple actor that records all messages it receives.

Usage pattern:

- start the actor in a TaskGroup
- send messages to its PID
- inspect `TestActor.messages`

Note: in pytest, classes named `Test*` may be picked up as test classes; this project’s tests already accept the resulting collection warnings. If that becomes annoying, rename the helper actor to something like `MailboxCollectorActor`.

## Tips for writing good async tests

- Prefer explicit timeouts over “sleep a bit and hope”.
- Keep tests deterministic:
  - avoid global registries unless you clean them up
  - prefer local mailboxes or unique names
- If you test supervision behavior, test outcomes (restart happened) rather than timing (restart happened in exactly X ms).

## Coverage

The project uses `pytest-cov` (see `pyproject.toml` / `pytest.ini`). After running tests, HTML coverage output is generated in `htmlcov/`.
