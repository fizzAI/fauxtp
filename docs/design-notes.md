# Design notes

This document is “why things are the way they are”.

It is not a full architecture spec (see [`ARCHITECTURE.md`](ARCHITECTURE.md)), but it captures the most important constraints and tradeoffs as the code exists today.

## Goals

- Make async Python concurrency feel less “free-floating tasks everywhere”.
- Provide OTP-ish primitives:
  - mailbox + selective receive
  - GenServer-style dispatch
  - supervisor restart strategies
- Keep the surface area small and comprehensible.

## Non-goals

- Being the BEAM (performance, distribution, preemptive scheduling).
- Transparent multi-node clustering.
- Lock-free, highly optimized mailboxes.

## Structured concurrency as a core constraint

A deliberate design choice is to require actors to start inside an AnyIO TaskGroup:

- [`python.Actor.start()`](src/fauxtp/actor/base.py:137)
- [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68)

Why:

- You always know what “owns” a process.
- Cancellation propagates explicitly via TaskGroup scopes.
- Supervisors can “own child lifetimes” the way OTP supervisors do.

This is also why examples use:

```python
async with anyio.create_task_group() as tg:
    pid = await MyActor.start(task_group=tg)
```

Rather than any hidden background-task spawning.

## Failure model vs Python task exceptions

In raw AnyIO/asyncio, an exception in a task usually cancels sibling tasks and bubbles up to a parent TaskGroup.

OTP is different: failures are normal; supervisors decide what to do.

`fauxtp` chooses an OTP-ish approach:

- actor tasks catch exceptions internally
- a failure is reported via an `on_exit` callback provided to [`python.Actor.start_link()`](src/fauxtp/actor/base.py:68)
- supervisors use `on_exit` to translate failures into `"$child_down"` mailbox messages (see [`python.Supervisor._start_child()`](src/fauxtp/supervisor/base.py:77))

This keeps failure handling inside the “actor world” rather than relying on TaskGroup exception bubbling.

## PID identity and encapsulation

Today, a PID includes a mailbox reference:

- [`python.PID._mailbox`](src/fauxtp/primitives/pid.py:16)

This makes the system simple and fast to prototype, but it is “less opaque” than OTP PIDs.

To centralize and isolate this design choice, mailbox access is kept in the messaging layer:

- [`src/fauxtp/messaging.py`](src/fauxtp/messaging.py)

If the project later adds transports (remote nodes) or stricter encapsulation, `messaging.py` is the obvious “swap point”.

## `call()` design (reply-to mailbox)

`call()` is implemented as:

- allocate an ephemeral mailbox
- send `("$call", ref, reply_to_pid, request)`
- wait for `("$reply", ref, reply)` in the ephemeral mailbox

See [`python.call()`](src/fauxtp/messaging.py:25).

Tradeoffs:

- Pros:
  - very small implementation
  - doesn’t require global “self pid” context
  - easy to correlate replies
- Cons:
  - not the same as OTP’s “call from a process mailbox”
  - doesn’t model mailbox ordering guarantees between calls and other messages

This is a pragmatic approach for the current project scope.

## Selective receive tradeoffs

Mailbox receive is implemented by scanning the internal deque:

- [`python.Mailbox.receive()`](src/fauxtp/primitives/mailbox.py:28)

This provides selective receive semantics, but it has an inherent cost:

- matching is O(N) in buffered messages (per receive attempt)

This mirrors OTP’s selective receive reality: it is powerful but should be used with discipline.

## Supervisor behavior and restart storms

Supervisor restarts are controlled by:

- strategy: [`python.RestartStrategy`](src/fauxtp/supervisor/child_spec.py:11)
- per-child restart type: [`python.RestartType`](src/fauxtp/supervisor/child_spec.py:18)
- rate limits: [`python.Supervisor.max_restarts`](src/fauxtp/supervisor/base.py:31) and [`python.Supervisor.max_seconds`](src/fauxtp/supervisor/base.py:32)

If too many restarts happen in a window, the supervisor raises [`python.MaxRestartsExceeded`](src/fauxtp/supervisor/base.py:21).

This is a safety mechanism: “don’t restart forever” is part of OTP’s robustness story.

## Intended evolution

Reasonable next steps (not implemented yet):

- A public supervisor control API (`which_children`, `terminate_child`, etc.) rather than sending internal command messages.
- Explicit “exit reason” types instead of string heuristics (especially for `TRANSIENT`).
- Optional monitors/links (OTP-style relationships).
- Better observability (structured logging/tracing for message flows).
