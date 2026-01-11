# GenServer API

## GenServer

`fauxtp.actor.genserver.GenServer`

Generic Server implementation. Inherits from `Actor`.

### Methods to Override

#### `async handle_call(self, request: R, from_ref: Ref, state: S) -> tuple[R, S]`
Handle synchronous request. Returns `(reply, new_state)`.

#### `async handle_cast(self, request: R, state: S) -> S`
Handle asynchronous request. Returns `new_state`.

#### `async handle_info(self, message: R, state: S) -> S`
Handle other messages. Returns `new_state`.

### Background Tasks

GenServers can spawn long-running work without blocking their mailbox, using
[`GenServer.start_background_task()`](src/fauxtp/actor/genserver.py:93).

When the background task completes, the GenServer will receive one of:

- `(GenServer.TASK_SUCCESS, task_pid, result)`
- `(GenServer.TASK_FAILURE, task_pid, reason)`

You can handle these by overriding:

#### `async handle_task_success(self, task_ref: Ref | None, task_pid: PID, result: Any, state: S) -> S`
Called when a background task started via `start_background_task()` succeeds.

#### `async handle_task_failure(self, task_ref: Ref | None, task_pid: PID, reason: Any, state: S) -> S`
Called when a background task started via `start_background_task()` fails or is cancelled.

### Inherited Methods
See [Actor API](actor.md) for inherited methods like `start`, `start_link`, `init`, and `terminate`.
