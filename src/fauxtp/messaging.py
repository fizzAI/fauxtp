"""Public messaging API (send/call/cast) for fauxtp.

This module provides the primary messaging interface that routes messages
through the router layer, enabling both local and (future) distributed routing.
"""

from __future__ import annotations

from typing import Any

import uuid

from .router import get_default_router, register_pid_mailbox, unregister_pid_mailbox
from .primitives.mailbox import Mailbox
from .primitives.pattern import ANY
from .primitives.pid import PID, Ref


async def send(target: PID, message: Any) -> None:
    """Send a message to an actor's mailbox.
    
    The message is routed through the default router, which handles
    both local and (future) remote delivery.
    
    Args:
        target: The destination PID
        message: The message to deliver
        
    Raises:
        PIDNotFound: If the target PID cannot be found for routing
        RoutingError: If routing fails
    """
    router = get_default_router()
    await router.route(target, message)


async def cast(target: PID, request: Any) -> None:
    """Send request, don't wait for reply (fire-and-forget).
    
    This is an asynchronous send that returns immediately.
    The request is wrapped in a ("$cast", request) tuple.
    
    Args:
        target: The destination PID
        request: The request to send
    """
    await send(target, ("$cast", request))


async def call(target: PID, request: Any, timeout: float = 5.0) -> Any:
    """
    Send request and wait for reply (synchronous request/reply).
    
    This creates an ephemeral reply mailbox, sends a call message with a
    unique Ref for correlation, and waits for the reply.
    
    The call message format is: ("$call", ref, reply_pid, request)
    The expected reply format is: ("$reply", ref, result)
    
    Args:
        target: PID of the target GenServer
        request: The request to send
        timeout: Maximum time to wait for reply (seconds)

    Returns:
        The reply from the GenServer

    Raises:
        ReceiveTimeout: If no reply is received within timeout
        PIDNotFound: If the target PID cannot be found
        RoutingError: If routing fails
    """
    ref = Ref()

    # Create a temporary mailbox and PID for receiving the reply
    reply_mailbox = Mailbox()
    reply_pid = PID(_id=uuid.uuid4())
    
    # Register the temporary mailbox so send() can route to it
    register_pid_mailbox(reply_pid.id, reply_mailbox)
    
    try:
        await send(target, ("$call", ref, reply_pid, request))

        return await reply_mailbox.receive(
            (("$reply", ref, ANY), lambda reply: reply),
            timeout=timeout,
        )
    finally:
        # Clean up the temporary mailbox registration
        unregister_pid_mailbox(reply_pid.id)
