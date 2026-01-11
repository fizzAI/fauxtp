"""Test utilities for fauxtp."""

import anyio
from typing import Any, Callable, TypeVar
from ..actor.base import Actor
from ..primitives.pattern import ANY

T = TypeVar('T')


async def with_timeout(coro, timeout: float = 1.0):
    """
    Run a coroutine with a timeout.
    
    Raises TimeoutError if timeout exceeded.
    """
    with anyio.fail_after(timeout):
        return await coro


async def assert_receives(actor: Actor, *patterns, timeout: float = 1.0) -> Any:
    """
    Assert that an actor receives a matching message within timeout.
    
    Raises TimeoutError if no match found within timeout.
    """
    return await with_timeout(
        actor.receive(*patterns, timeout=timeout),
        timeout=timeout
    )


async def wait_for(condition: Callable[[], bool], timeout: float = 1.0, interval: float = 0.01):
    """
    Wait for a condition to become true.
    
    Args:
        condition: A callable that returns a boolean
        timeout: Maximum time to wait
        interval: How often to check the condition
        
    Raises:
        TimeoutError: If condition doesn't become true within timeout
    """
    deadline = anyio.current_time() + timeout
    
    while anyio.current_time() < deadline:
        if condition():
            return
        await anyio.sleep(interval)
    
    raise TimeoutError(f"Condition not met within {timeout}s")


class TestActor(Actor):
    """
    A simple test actor that collects messages.

    Useful for testing message flows.
    """

    # Prevent pytest from trying to collect this as a test class when imported in tests.
    __test__ = False

    def __init__(self):
        super().__init__()
        self.messages: list[Any] = []
    
    async def init(self):
        return {"messages": []}
    
    async def run(self, state):
        """Collect all incoming messages."""
        msg = await self.receive((ANY, lambda m: m))
        state["messages"].append(msg)
        self.messages.append(msg)
        return state
    
    def get_messages(self) -> list[Any]:
        """Get all received messages."""
        return self.messages.copy()
    
    def clear_messages(self):
        """Clear all received messages."""
        self.messages.clear()