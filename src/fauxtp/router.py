"""PID Router with global registry and routing scaffolding for distributed messaging.

This module provides:
- A global PID -> Mailbox registry for local actors
- A Router abstraction for extensible message routing
- LocalRouter for in-process message delivery
- Scaffolding for future distributed routing (RemoteRouter, etc.)
"""

from __future__ import annotations

from typing_extensions import override
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .primitives.mailbox import Mailbox
    from .primitives.pid import PID


# Global registry: PID UUID -> Mailbox
# This is module-level state for the local node
_local_mailbox_registry: dict[uuid.UUID, Mailbox] = {}


def register_pid_mailbox(pid_uuid: uuid.UUID, mailbox: Mailbox) -> None:
    """Register a PID's mailbox in the global local registry.
    
    Called by actors when they start up.
    """
    _local_mailbox_registry[pid_uuid] = mailbox


def unregister_pid_mailbox(pid_uuid: uuid.UUID) -> None:
    """Unregister a PID's mailbox from the global local registry.
    
    Called when an actor terminates.
    """
    _local_mailbox_registry.pop(pid_uuid, None)


def get_local_mailbox(pid_uuid: uuid.UUID) -> Mailbox | None:
    """Get the mailbox for a PID from the local registry.
    
    Returns None if the PID is not registered locally.
    """
    return _local_mailbox_registry.get(pid_uuid)


def is_local_pid(pid_uuid: uuid.UUID) -> bool:
    """Check if a PID is registered in the local mailbox registry."""
    return pid_uuid in _local_mailbox_registry


class Router(ABC):
    """Abstract base class for message routers.
    
    A router determines how to deliver a message to a target PID.
    Subclasses can implement different routing strategies:
    - LocalRouter: In-process delivery using the global registry
    - RemoteRouter: Network delivery to other nodes (future)
    - MultiRouter: Delegates to local or remote based on PID (future)
    """
    
    @abstractmethod
    async def route(self, target: PID, message: Any) -> None:
        """Route a message to the target PID.
        
        Args:
            target: The destination PID
            message: The message to deliver
            
        Raises:
            PIDNotFound: If the PID cannot be routed
            RoutingError: If routing fails for other reasons
        """
        ...
    
    @abstractmethod
    def can_route(self, target: PID) -> bool:
        """Check if this router can route to the given PID."""
        ...


class PIDNotFound(Exception):
    """Raised when a PID cannot be found for routing."""
    pass


class RoutingError(Exception):
    """Raised when message routing fails."""
    pass


class LocalRouter(Router):
    """Router for local in-process message delivery.
    
    Uses the global _local_mailbox_registry to look up mailboxes.
    """
    
    @override
    async def route(self, target: PID, message: Any) -> None:
        """Deliver message to a local PID's mailbox.
        
        Args:
            target: The destination PID (must be local)
            message: The message to deliver
            
        Raises:
            PIDNotFound: If the PID is not registered locally
        """
        from .primitives.pid import PID
        
        if not isinstance(target, PID):
            raise TypeError(f"Expected PID, got {type(target).__name__}")
        
        mailbox = get_local_mailbox(target.id)
        if mailbox is None:
            raise PIDNotFound(f"PID {target.id} not found in local registry")
        
        await mailbox.put(message)
    
    @override
    def can_route(self, target: PID) -> bool:
        """Check if the target PID is registered locally."""
        from .primitives.pid import PID
        
        if not isinstance(target, PID):  # pyright: ignore[reportUnnecessaryIsInstance]
            return False  # pyright: ignore[reportUnreachable]
        return is_local_pid(target.id)


# Default router instance - can be swapped out for distributed scenarios
_default_router: Router = LocalRouter()


def get_default_router() -> Router:
    """Get the default router for message delivery."""
    return _default_router


def set_default_router(router: Router) -> None:
    """Set the default router (useful for testing or distributed setups).
    
    Args:
        router: The router to use as default
    """
    global _default_router
    _default_router = router


class MultiRouter(Router):
    """Router that delegates to other routers based on PID type/location.
    
    This is scaffolding for future distributed support.
    Currently only supports local routing.
    
    Future extensions:
    - Check if PID is local or remote
    - Delegate to LocalRouter for local PIDs
    - Delegate to RemoteRouter for remote PIDs (network delivery)
    """
    
    def __init__(self, local_router: Router | None = None) -> None:
        self._local_router = local_router or LocalRouter()
        # Future: self._remote_router = remote_router

    
    @override
    async def route(self, target: PID, message: Any) -> None:
        """Route message using the appropriate sub-router.
        
        Currently only handles local routing.
        """
        # For now, all PIDs are local
        # Future: check if target is local or remote
        await self._local_router.route(target, message)
    
    @override
    def can_route(self, target: PID) -> bool:
        """Check if any sub-router can handle this PID."""
        # For now, only local routing is supported
        return self._local_router.can_route(target)
