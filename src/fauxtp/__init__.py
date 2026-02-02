"""Erlang/OTP-Inspired Concurrency for Python Async."""

from .primitives.pid import PID, Ref
from .primitives.mailbox import Mailbox, ReceiveTimeout
from .primitives.pattern import ANY, IGNORE
from .actor.base import Actor
from .actor.genserver import GenServer
from .registry import Registry
from .supervisor import Supervisor, ChildSpec
from .messaging import send, call, cast
from .router import (
    Router,
    LocalRouter,
    MultiRouter,
    PIDNotFound,
    RoutingError,
    register_pid_mailbox,
    unregister_pid_mailbox,
    get_local_mailbox,
    is_local_pid,
)

__all__ = [
    # Core primitives
    "PID",
    "Ref",
    "Mailbox",
    "ReceiveTimeout",
    "ANY",
    "IGNORE",
    # Actors
    "Actor",
    "GenServer",
    # Registry
    "Registry",
    #Supervisor
    "Supervisor",
    "ChildSpec",
    # Messaging
    "send",
    "call",
    "cast",
    # Routing
    "Router",
    "LocalRouter",
    "MultiRouter",
    "PIDNotFound",
    "RoutingError",
    "register_pid_mailbox",
    "unregister_pid_mailbox",
    "get_local_mailbox",
    "is_local_pid",
]
