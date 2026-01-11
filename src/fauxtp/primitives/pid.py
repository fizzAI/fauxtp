"""Process identifiers and references for the actor system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from typing_extensions import override
import uuid

if TYPE_CHECKING:
    from .mailbox import Mailbox


@dataclass(frozen=True, slots=True)
class PID:
    """Process identifier. Opaque handle to an actor."""
    _id: uuid.UUID
    _mailbox: Mailbox  # Internal, not for direct use

    @override
    def __hash__(self):
        return hash(self._id)


@dataclass(frozen=True, slots=True)  
class Ref:
    """Unique reference for request/reply correlation."""
    _id: uuid.UUID = field(default_factory=uuid.uuid4)