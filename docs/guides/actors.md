# Actors

Actors are the fundamental unit of concurrency in `fauxtp`. Each actor is a lightweight process (implemented as an AnyIO task) with its own private state and a mailbox for receiving messages.

## Core Concepts

- **Isolation**: Actors do not share state. They communicate exclusively through message passing.
- **Mailbox**: Every actor has a mailbox that buffers incoming messages.
- **PID**: A Process Identifier used to address and send messages to an actor.

## Creating an Actor

To create an actor, inherit from `fauxtp.actor.base.Actor` and implement the `loop` method.

```python
from fauxtp.actor.base import Actor
import anyio

class MyActor(Actor):
    async def loop(self):
        while True:
            # Wait for a message
            msg = await self.receive()
            print(f"Received: {msg}")

async def main():
    async with anyio.create_task_group() as tg:
        pid = await MyActor.start(task_group=tg)
        await pid.send("Hello!")

anyio.run(main)
```

## Pattern Matching

`fauxtp` encourages the use of Python's `match` statement for handling messages, similar to Erlang's `receive`.

```python
async def loop(self):
    while True:
        match await self.receive():
            case ("ping", sender_pid):
                await sender_pid.send("pong")
            case "stop":
                break
```

## Lifecycle

Actors are started within an AnyIO `TaskGroup`. When the `TaskGroup` exits, all actors started within it are cancelled. You can also stop an actor by returning from its `loop` method or by calling `pid.stop()`.