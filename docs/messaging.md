# Messaging

Messaging is the primary interface to running processes.

The public functions live in [`src/fauxtp/messaging.py`](src/fauxtp/messaging.py) and are re-exported from [`src/fauxtp/__init__.py`](src/fauxtp/__init__.py:1).

- [`python.send()`](src/fauxtp/messaging.py:13): send any message to a PID
- [`python.cast()`](src/fauxtp/messaging.py:18): conventional fire-and-forget message
- [`python.call()`](src/fauxtp/messaging.py:25): request/reply message with timeout and correlation

## PIDs, mailboxes, and boundaries

A [`python.PID`](src/fauxtp/primitives/pid.py:8) is an “address” for a process.

Internally it currently includes a reference to the mailbox implementation. The messaging layer exists to:

- centralize mailbox access behind a stable API
- keep higher-level modules consistent (e.g. [`python.GenServer`](src/fauxtp/actor/genserver.py:15) replies using [`python.send()`](src/fauxtp/messaging.py:13))
- provide a place to evolve transports later (e.g. remote nodes)

## `send(pid, message)`

Signature: [`python.send()`](src/fauxtp/messaging.py:13)

- Delivers `message` to `pid`’s mailbox.
- Does not expect a reply.
- Does not impose a message schema (you can send any Python object).

Recommended convention: use tagged tuples or small immutable payloads:

```python
await send(pid, ("event", "user_signup", {"id": 123}))
await send(pid, ("shutdown",))
```

## `cast(pid, request)`

Signature: [`python.cast()`](src/fauxtp/messaging.py:18)

This is a convention borrowed from OTP/GenServer: a cast is “fire and forget”. It wraps your request as:

- `("$cast", request)`

You typically only `cast()` to processes that implement [`python.GenServer`](src/fauxtp/actor/genserver.py:15), because `GenServer.run()` knows how to dispatch cast messages.

Example:

```python
await cast(counter_pid, ("set", 100))
await cast(counter_pid, "reset")
```

## `call(pid, request, timeout=...)`

Signature: [`python.call()`](src/fauxtp/messaging.py:25)

A call is synchronous request/reply:

- A unique correlation ref is created: [`python.Ref`](src/fauxtp/primitives/pid.py:19)
- A temporary reply mailbox is allocated
- The request is sent in this shape:

  `("$call", ref, reply_to_pid, request)`

- The caller then waits for a reply message shaped:

  `("$reply", ref, reply_value)`

If the timeout expires, [`python.ReceiveTimeout`](src/fauxtp/primitives/mailbox.py:85) is raised by the reply mailbox.

Example:

```python
value = await call(counter_pid, "get", timeout=1.0)
value = await call(counter_pid, ("add", 5))
```

### What `call()` is (and is not)

- It is *not* “the calling process’s mailbox” in the OTP sense.
- It is a “reply-to mailbox” pattern. That is good enough for many practical cases and keeps the API simple.

## Message shapes used by GenServer

[`python.GenServer.run()`](src/fauxtp/actor/genserver.py:25) treats messages as:

- Calls: `("$call", Ref, PID, ANY)`
- Casts: `("$cast", ANY)`
- Everything else: info

This is why mixing “raw send” with a GenServer can be useful: any message not matching call/cast gets routed to [`python.GenServer.handle_info()`](src/fauxtp/actor/genserver.py:72).

## Designing message protocols

### Prefer explicit tags

Instead of sending untagged dicts everywhere:

- good: `("user", "create", payload)`
- good: `("kv", "put", key, value)`
- avoid: `{"action": "...", ...}` (works but tends to grow messy)

### Keep messages versionable

If you expect evolution, put a “tag + version” or separate message types:

- `("cmd_v1", ...)`
- `("cmd", 1, ...)`

### Don’t send mutable shared state

Avoid sending objects that are simultaneously mutated by other tasks. Use copies or immutable structures.

## Observability note

Today there is no built-in tracing/logging for messages. If you want visibility, wrap `send`/`call`/`cast` at your application boundary or add logging inside your actors’ handlers.
