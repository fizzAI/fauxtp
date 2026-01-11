"""Erlang/OTP-Inspired Concurrency for Python Async."""

from .primitives.pid import PID, Ref
from .primitives.mailbox import Mailbox, ReceiveTimeout
from .primitives.pattern import ANY, IGNORE
from .actor.base import Actor
from .actor.genserver import GenServer
from .supervisor.child_spec import ChildSpec, RestartType, RestartStrategy
from .supervisor.base import Supervisor, MaxRestartsExceeded
from .registry.local import register, unregister, whereis, registered, Registry
from .messaging import send, call, cast

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
    # Supervision
    "Supervisor",
    "ChildSpec",
    "RestartType",
    "RestartStrategy",
    "MaxRestartsExceeded",
    # Registry
    "Registry",
    "register",
    "unregister",
    "whereis",
    "registered",
    # Messaging
    "send",
    "call",
    "cast",
]
