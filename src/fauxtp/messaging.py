"""Public messaging API (send/call/cast) for fauxtp."""

from __future__ import annotations

from typing import Any

import uuid

from .primitives.mailbox import Mailbox
from .primitives.pattern import ANY
from .primitives.pid import PID, Ref


async def send(target: PID, message: Any) -> None:
    """Send a message to an actor's mailbox."""
    await target._mailbox.put(message)


async def cast(target: PID, request: Any) -> None:
    """Send request, don't wait for reply."""
    await send(target, ("$cast", request))


async def call(target: PID, request: Any, timeout: float = 5.0) -> Any:
    """
    Send request and wait for reply.

    This uses an ephemeral reply mailbox (a "reply-to" PID) and correlates replies
    with a unique Ref.

    Args:
        target: PID of the target GenServer
        request: The request to send
        timeout: Maximum time to wait for reply (seconds)

    Returns:
        The reply from the GenServer

    Raises:
        ReceiveTimeout: If no reply is received within timeout
    """
    ref = Ref()

    # Create a temporary mailbox for receiving the reply. Use a fresh UUID for the
    # PID identity to avoid conflating the PID and Ref identity spaces.
    reply_mailbox = Mailbox()
    reply_pid = PID(_id=uuid.uuid4(), _mailbox=reply_mailbox)

    await send(target, ("$call", ref, reply_pid, request))

    return await reply_mailbox.receive(
        (("$reply", ref, ANY), lambda reply: reply),
        timeout=timeout,
    )