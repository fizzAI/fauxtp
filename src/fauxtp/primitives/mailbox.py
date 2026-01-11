"""Actor mailbox with selective receive support."""

from collections import deque
import inspect
from typing import Any, Callable, TypeVar

import anyio

T = TypeVar('T')


class Mailbox:
    """
    Actor mailbox with selective receive support.
    
    Not trying to be clever - just a deque that we scan.
    """
    def __init__(self, max_size: int = 0):  # 0 = unbounded
        self._buffer: deque[Any] = deque()
        self._signal = anyio.Event()
        self._max_size = max_size
    
    async def put(self, message: Any) -> None:
        """Deliver a message to this mailbox."""
        # Optional: backpressure if bounded
        self._buffer.append(message)
        self._signal.set()
    
    async def receive(
        self,
        *patterns: tuple[Any, Callable[..., T]],
        timeout: float | None = None,
    ) -> T:
        """
        For internal use only.

        Receive a message matching one of the patterns from this mailbox.

        Each pattern is a (matcher, handler) tuple.
        Matcher can be:
          - A type: matches isinstance
          - A tuple: matches structure like ("tag", ANY, str)
          - A callable: matches if returns truthy
          - ANY: matches everything

        Handler receives extracted values and returns result.
        """
        with anyio.move_on_after(timeout) as scope:
            while True:
                # Scan buffer for match
                for i, msg in enumerate(self._buffer):
                    for matcher, handler in patterns:
                        if (extracted := self._match(msg, matcher)) is not None:
                            del self._buffer[i]
                            return await self._call_handler(handler, extracted)

                # No match found, wait for new messages
                await self._signal.wait()
                self._signal = anyio.Event()

        # Timeout / cancellation
        if scope.cancelled_caught:
            raise ReceiveTimeout(f"No matching message within {timeout}s")

        # Defensive: in practice move_on_after either returns normally or sets cancelled_caught.
        raise ReceiveTimeout(f"No matching message within {timeout}s")
    
    def _match(self, msg: Any, pattern: Any) -> tuple[Any, ...] | None:
        """Returns extracted values if match, None otherwise."""
        # Import here to avoid circular imports
        from .pattern import match_pattern
        return match_pattern(msg, pattern)
    
    async def _call_handler(self, handler: Callable[..., T], extracted: tuple[Any, ...]) -> T:
        """Call handler with extracted values."""
        if len(extracted) == 0:
            result = handler()
        elif len(extracted) == 1:
            result = handler(extracted[0])
        else:
            result = handler(*extracted)

        if inspect.isawaitable(result):
            return await result  # type: ignore[misc]
        return result  # type: ignore[return-value]


class ReceiveTimeout(Exception):
    """Raised when receive() times out."""
    pass