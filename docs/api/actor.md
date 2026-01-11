# Actor API

## Actor

`fauxtp.actor.base.Actor`

Base actor class. Subclass and implement `run()`.

### Methods

#### `async init(self) -> Any`
Initialize actor state (async). Returns initial state.

Constructor args passed to [`Actor.start()`](docs/api/actor.md:23) / [`Actor.start_link()`](docs/api/actor.md:26)
go to `__init__()`, not to `init()`.

#### `abstract async run(self, state: Any) -> Any`
Main actor loop body. Called repeatedly. Should await `receive()` and handle messages. Returns new state.

#### `async terminate(self, reason: str, state: Any) -> None`
Cleanup when actor stops. Override this to perform any necessary cleanup.

#### `async receive(self, *patterns: tuple[Any, MaybeAwaitableCallable], timeout: float | None = None) -> Any`
Receive from this actor's mailbox. Each pattern is a `(matcher, handler)` tuple.

#### `classmethod async start(cls, *args, task_group: TaskGroup, **kwargs) -> PID`
Start this actor inside the given AnyIO TaskGroup and return its PID.

`*args` / `**kwargs` are passed to the actor's constructor (`__init__`).

#### `classmethod async start_link(cls, *args, task_group: TaskGroup, on_exit: Callable[[PID, str], Awaitable[None]] | None = None, **kwargs) -> ActorHandle`
Start this actor inside the given AnyIO TaskGroup. Returns an `ActorHandle`.

`*args` / `**kwargs` are passed to the actor's constructor (`__init__`).

#### `def stop(self, reason: str = "normal")`
Manually exits the actor with a given reason.

#### `def start_soon_child(self, fn: MaybeAwaitableCallable, *args, name: str | None = None)`
Starts a task in the actor's child task group.

#### `async spawn_child_actor(self, actor_cls: type[Actor], *args, on_exit: MaybeAwaitableCallable | None = None, **kwargs) -> ActorHandle`
Spawns a child actor supervised by this actor.

### Properties

#### `pid: PID`
The PID of the running actor.

#### `children: TaskGroup`
A TaskGroup owned by this actor, cancelled when the actor exits.

---

## Task

`fauxtp.actor.task.Task`

Generic actor wrapper that runs an asynchronous function.

### Methods

#### `classmethod async spawn(cls, func: MaybeAwaitableCallable, task_group: TaskGroup) -> TaskHandle`
Spawns a task and returns a `TaskHandle`.

#### `classmethod async spawn_and_notify(cls, func: MaybeAwaitableCallable, task_group: TaskGroup, parent_pid: PID, success_message_name: str = "$$success", failure_message_name: str = "$$failure") -> TaskHandle`
Spawns a task and notifies the parent PID on completion.

---

## ActorHandle

`fauxtp.actor.base.ActorHandle`

Handle to a running actor task.

### Attributes
- `pid: PID`
- `cancel_scope: anyio.CancelScope`

---

## TaskHandle

`fauxtp.actor.task.TaskHandle`

Wrapper around `ActorHandle` for Tasks.

### Methods

#### `async join(self) -> Any`
Wait for Task completion and return its value, or raise on failure.

#### `pid: PID`
PID of the underlying Task.

#### `cancel() -> None`
Cancel the underlying Task.
