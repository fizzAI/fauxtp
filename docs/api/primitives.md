# Primitives API

## PID

`fauxtp.primitives.pid.PID`

Process identifier. Opaque handle to an actor.

---

## Ref

`fauxtp.primitives.pid.Ref`

Unique reference for request/reply correlation.

---

## Messaging

`fauxtp.messaging`

### `async send(target: PID, message: Any) -> None`
Send a message to an actor's mailbox.

### `async cast(target: PID, request: Any) -> None`
Send request to a GenServer, don't wait for reply.

### `async call(target: PID, request: Any, timeout: float = 5.0) -> Any`
Send request to a GenServer and wait for reply.

---

## Pattern Matching

`fauxtp.primitives.pattern`

The pattern matching system is used by `receive()` to selectively process messages from an actor's mailbox.

### Matchers

A pattern can be composed of several types of matchers:

- **Literal Values**: Matches if the message is exactly equal to the value (e.g., `"ping"`, `123`).
- **Types**: Matches if the message is an instance of the type (e.g., `str`, `int`, `dict`). The value is extracted and passed to the handler.
- **Tuples**: Matches if the message is a tuple of the same length and each element matches its corresponding sub-pattern.
- **`ANY`**: A special matcher that matches any value and extracts it.
- **`IGNORE`** (or `_`): A special matcher that matches any value but does **not** extract it.

### Examples

```python
from fauxtp.primitives.pattern import ANY, IGNORE

# Match a specific tag and extract the payload
# Message: ("data", 42)
pattern = ("data", ANY)
# Result: (42,) extracted

# Match a structure but ignore part of it
# Message: ("event", "user_login", "127.0.0.1")
pattern = ("event", IGNORE, ANY)
# Result: ("127.0.0.1",) extracted

# Match by type
# Message: {"key": "value"}
pattern = dict
# Result: ({"key": "value"},) extracted

# Nested matching
# Message: ("msg", ("sub", 1))
pattern = ("msg", ("sub", int))
# Result: (1,) extracted
```

### `ANY`
Matches any value and extracts it.

### `IGNORE` or `_`
Matches any value but does not extract it.

---

## Registry

`fauxtp.registry.local`

### `register(name: str, pid: PID) -> bool`
Register a process globally by name. Returns `True` if successful.

### `unregister(name: str) -> bool`
Unregister a process name globally.

### `whereis(name: str) -> Optional[PID]`
Look up a process globally by name. Returns `PID` if found, `None` otherwise.

### `registered() -> list[str]`
Get list of all registered process names.