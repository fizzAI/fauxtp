# Testing API

## Helpers

`fauxtp.testing.helpers`

### `async with_timeout(coro, timeout: float = 1.0)`
Run a coroutine with a timeout. Raises `TimeoutError` if timeout exceeded.

### `async assert_receives(actor: Actor, *patterns, timeout: float = 1.0) -> Any`
Assert that an actor receives a matching message within timeout.

### `async wait_for(condition: Callable[[], bool], timeout: float = 1.0, interval: float = 0.01)`
Wait for a condition to become true.

---

## TestActor

`fauxtp.testing.helpers.TestActor`

A simple test actor that collects messages.

### Methods

#### `def get_messages(self) -> list[Any]`
Get all received messages.

#### `def clear_messages(self)`
Clear all received messages.