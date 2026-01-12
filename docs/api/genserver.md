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

#### `async handle_task_end(self, pid: PID, result: dict[str, Any], state: S) -> S`
Handle task completion or failure. `result` is `{"status": "ok"|"error", "value": res|err}`.

### Public Methods

#### `async spawn_task(self, func: Callable, *args: Any, **kwargs: Any) -> PID | None`
Spawn a new task managed by this GenServer. Returns the task's PID, or `None` if the task limit is reached.

#### `set_max_tasks(self, limit: int | None) -> None`
Set the maximum number of concurrent tasks.

### Inherited Methods
See [Actor API](actor.md) for inherited methods like `start`, `start_link`, `init`, and `terminate`.