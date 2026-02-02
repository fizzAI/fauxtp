"""Process identifiers and references for the actor system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from typing_extensions import override
import uuid

if TYPE_CHECKING:
    pass  # No longer depends on Mailbox


@dataclass(frozen=True, slots=True)
class PID:
    """Process identifier. Opaque handle to an actor.
    
    The PID is immutable and contains only routing information.
    It does NOT contain the mailbox - mailboxes are stored in the
    global registry (see router.py).
    
    Attributes:
        id: The unique UUID identifying this process
        node: Optional node identifier for distributed routing (future)
    """
    _id: uuid.UUID = field(repr=False)
    _node: str | None = field(default=None, repr=False)

    @property
    def id(self) -> uuid.UUID:
        """Get the process identifier UUID."""
        return self._id

    @property
    def node(self) -> str | None:
        """Get the node identifier for distributed routing (None for local)."""
        return self._node
    
    def is_local(self) -> bool:
        """Check if this PID refers to a local process."""
        return self._node is None

    @override
    def __hash__(self) -> int:
        return hash((self._id, self._node))

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PID):
            return NotImplemented
        return self._id == other._id and self._node == other._node


@dataclass(frozen=True, slots=True)
class Ref:
    """Unique reference for request/reply correlation."""
    _id: uuid.UUID = field(default_factory=uuid.uuid4)
    
    @property
    def id(self) -> uuid.UUID:
        """Get the reference UUID."""
        return self._id
