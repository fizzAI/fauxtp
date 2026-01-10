# Primitives

This document covers the “small building blocks” that make up the actor system:

- [`python.PID`](src/fauxtp/primitives/pid.py:8) and [`python.Ref`](src/fauxtp/primitives/pid.py:19)
- [`python.Mailbox`](src/fauxtp/primitives/mailbox.py:10) (message queue + selective receive)
- Pattern matching with [`python.match_pattern()`](src/fauxtp/primitives/pattern.py:22), [`python.ANY`](src/fauxtp/primitives/pattern.py:11), and [`python.IGNORE`](src/fauxtp/primitives/pattern.py:19)

## PID and Ref

### PID

Implementation: [`python.class PID`](src/fauxtp/primitives/pid.py:8)

A PID is an opaque handle to a running actor/process. You use it to:

- send messages: [`python.send()`](src/fauxtp/messaging.py:13)
- call GenServers: [`python.call()`](src/fauxtp/messaging.py:25)
- cast to GenServers: [`python.cast()`](src/fauxtp/messaging.py:18)

Notes:

- Equality/hash are based on `_id` ([`src/fauxtp/primitives/pid.py`](src/fauxtp/primitives/pid.py) lines 9–15).
- The PID also carries an internal mailbox reference. You should treat it as implementation detail and go through messaging functions.

### Ref

Implementation: [`python.class Ref`](src/fauxtp/primitives/pid.py:19)

A Ref is a unique reference used for correlating replies in request/reply messaging.

- `call()` creates a [`python.Ref`](src/fauxtp/primitives/pid.py:19).
- GenServer replies include the same ref, allowing `call()` to match the correct reply.

## Mailbox

Implementation: [`python.class Mailbox`](src/fauxtp/primitives/mailbox.py:10)

A mailbox is:

- a buffer of pending messages
- a “signal” used to wake receivers when new messages arrive
- the core of “selective receive”: you can wait for the *first* message that matches a pattern, not just FIFO order.

### `Mailbox.put(message)`

Signature: [`python.Mailbox.put()`](src/fauxtp/primitives/mailbox.py:21)

Appends to the mailbox and wakes any waiting receivers.

### `Mailbox.receive(*patterns, timeout=None)`

Signature: [`python.Mailbox.receive()`](src/fauxtp/primitives/mailbox.py:28)

Each pattern is a `(matcher, handler)` tuple:

- `matcher`: a pattern supported by [`python.match_pattern()`](src/fauxtp/primitives/pattern.py:22)
- `handler`: called with extracted values from the match

The mailbox scans its buffer for the first message that matches any matcher. When found:

- the message is removed from the buffer
- the handler is invoked and its return value is returned from `receive()`
- handlers can be sync or async; awaitables are detected via `inspect.isawaitable` ([`src/fauxtp/primitives/mailbox.py`](src/fauxtp/primitives/mailbox.py) lines 69–79)

### Timeouts

Timeouts raise [`python.ReceiveTimeout`](src/fauxtp/primitives/mailbox.py:85).

Example:

```python
from fauxtp import Mailbox, ANY, ReceiveTimeout

mailbox = Mailbox()
try:
    await mailbox.receive((ANY, lambda msg: msg), timeout=0.1)
except ReceiveTimeout:
    ...
```

### Selective receive semantics (important)

Because the mailbox scans the buffer for a match, it is possible to:

- leave unmatched messages in the mailbox while consuming later matching messages
- “reorder” consumption relative to strict FIFO

This is deliberate and mirrors OTP’s selective receive behavior.

Tradeoff: scanning is O(N * P) per receive attempt (N messages buffered, P patterns supplied), so avoid designs that accumulate huge backlogs.

## Pattern matching

Implementation: [`src/fauxtp/primitives/pattern.py`](src/fauxtp/primitives/pattern.py)

### Pattern values

- Match-any + extract: [`python.ANY`](src/fauxtp/primitives/pattern.py:11)
- Match-any + ignore/extract nothing: [`python.IGNORE`](src/fauxtp/primitives/pattern.py:19)

### `match_pattern(value, pattern)`

Signature: [`python.match_pattern()`](src/fauxtp/primitives/pattern.py:22)

Supported patterns include:

- `ANY`: extracts `(value,)`
- `IGNORE`: extracts `()`
- `type`: matches `isinstance(value, type)` and extracts `(value,)`
- tuples: matches tuple structure and extracts concatenated extracted values
- literals: matches by equality and extracts `()`

Examples:

- `match_pattern(("ping", 123), ("ping", ANY)) → (123,)`
- `match_pattern(("cmd", "x", "y"), ("cmd", IGNORE, ANY)) → ("y",)`

## Why these primitives matter

Everything else in the system composes these primitives:

- Actors are tasks that repeatedly `receive()` from their mailbox: [`python.Actor.receive()`](src/fauxtp/actor/base.py:44)
- GenServer is a structured receive/dispatch loop: [`python.GenServer.run()`](src/fauxtp/actor/genserver.py:25)
- Supervision is largely “start tasks + react to exits”: [`python.Supervisor`](src/fauxtp/supervisor/base.py:25)