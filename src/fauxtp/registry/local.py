"""Local process name registry."""

from typing import Dict, Optional
import threading
from ..primitives.pid import PID


class Registry:
    """
    Thread-safe local process registry.
    
    Maps names to PIDs for process discovery.
    """
    
    def __init__(self):
        self._names: Dict[str, PID] = {}
        self._lock = threading.Lock()
    
    def register(self, name: str, pid: PID) -> bool:
        """
        Register a process with a name.
        
        Returns True if successful, False if name already registered.
        """
        with self._lock:
            if name in self._names:
                return False
            self._names[name] = pid
            return True
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a process name.
        
        Returns True if successful, False if name not found.
        """
        with self._lock:
            if name not in self._names:
                return False
            del self._names[name]
            return True
    
    def whereis(self, name: str) -> Optional[PID]:
        """
        Look up a process by name.
        
        Returns PID if found, None otherwise.
        """
        with self._lock:
            return self._names.get(name)
    
    def registered(self) -> list[str]:
        """Return list of all registered names."""
        with self._lock:
            return list(self._names.keys())


# Global registry instance
_global_registry = Registry()


def register(name: str, pid: PID) -> bool:
    """Register a process globally by name."""
    return _global_registry.register(name, pid)


def unregister(name: str) -> bool:
    """Unregister a process name globally."""
    return _global_registry.unregister(name)


def whereis(name: str) -> Optional[PID]:
    """Look up a process globally by name."""
    return _global_registry.whereis(name)


def registered() -> list[str]:
    """Get list of all registered process names."""
    return _global_registry.registered()