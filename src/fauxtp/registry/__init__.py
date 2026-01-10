"""Process registry for named process lookup."""

from .local import Registry, register, unregister, whereis

__all__ = [
    "Registry",
    "register",
    "unregister",
    "whereis",
]