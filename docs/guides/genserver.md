# GenServers

`GenServer` (Generic Server) is a behavior module for implementing the server of a client-server relation. It abstracts away the common patterns of state management and message handling.

## Why use GenServer?

While you can build any actor using the base `Actor` class, `GenServer` provides:
- Standardized synchronous (`call`) and asynchronous (`cast`) communication.
- Built-in state management.
- Better integration with Supervisors.

## Implementation

To implement a `GenServer`, you need to define:
1. `init(self)`: Initializes the server state.
2. `handle_call(self, request, _from, state)`: Handles synchronous requests.
3. `handle_cast(self, request, state)`: Handles asynchronous requests.
4. `handle_info(self, msg, state)`: Handles all other messages.
5. `handle_task_end(self, pid, result, state)`: Handles completion of background tasks.

```python
from fauxtp import GenServer, call, cast

class Stack(GenServer):
    async def init(self):
        return []

    async def handle_call(self, request, _from, state):
        match request:
            case "pop":
                if not state:
                    return None, []
                val = state[0]
                return val, state[1:]
            case "peek":
                return state[0] if state else None, state

    async def handle_cast(self, request, state):
        match request:
            case ("push", item):
                return [item] + state
```

## Client API

- `call(pid, request)`: Sends a request and waits for a response.
- `cast(pid, request)`: Sends a request and returns immediately.

```python
pid = await Stack.start(task_group=tg)
await cast(pid, ("push", 1))
val = await call(pid, "pop") # 1
```

## State Immutability

It is highly recommended to treat the state as immutable. Instead of modifying the `state` object, always return a new state from your handlers.

## Background Tasks

`GenServer` provides a built-in way to spin off long-running tasks without blocking the main message loop.

### Spawning Tasks

Use `self.spawn_task(func, *args, **kwargs)` to start a background task.

> **Warning**: `spawn_task` cannot be called inside `init()`. It requires the server to be fully started.

### Handling Results

When a task finishes (successfully or with an error), `handle_task_end` is called.

```python
async def handle_task_end(self, pid, result, state):
    # result is {"status": "ok" | "error", "value": return_val | exception}
    if result["status"] == "ok":
        print(f"Task {pid} succeeded with {result['value']}")
    else:
        print(f"Task {pid} failed with {result['value']}")
    return state
```

### Task Limiting

You can limit the number of concurrent tasks using `self.set_max_tasks(limit)`. If the limit is reached, `spawn_task` returns `None`.