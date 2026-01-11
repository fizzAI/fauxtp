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

### Inherited Methods
See [Actor API](actor.md) for inherited methods like `start`, `start_link`, `init`, and `terminate`.