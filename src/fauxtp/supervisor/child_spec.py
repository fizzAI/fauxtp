"""Child specifications and restart strategies for supervisors."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..actor.base import Actor


class RestartStrategy(Enum):
    """Supervisor restart strategies."""
    ONE_FOR_ONE = auto()   # Only restart the failed child
    ONE_FOR_ALL = auto()   # Restart all children if one fails
    REST_FOR_ONE = auto()  # Restart failed child and all children started after it


class RestartType(Enum):
    """Child restart types."""
    PERMANENT = auto()   # Always restart
    TRANSIENT = auto()   # Restart only on abnormal exit
    TEMPORARY = auto()   # Never restart


@dataclass
class ChildSpec:
    """
    Specification for a supervised child actor.
    
    Attributes:
        id: Unique identifier for this child
        actor_class: The Actor class to instantiate
        args: Positional arguments for actor constructor
        kwargs: Keyword arguments for actor constructor
        restart: Restart behavior for this child
    """
    id: str
    actor_class: type["Actor"]  # type: ignore
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    restart: RestartType = RestartType.PERMANENT
    
    def __post_init__(self):
        """Validate the child spec."""
        if not self.id:
            raise ValueError("Child id cannot be empty")
        if not hasattr(self.actor_class, 'start'):
            raise ValueError(f"{self.actor_class} must be an Actor class")