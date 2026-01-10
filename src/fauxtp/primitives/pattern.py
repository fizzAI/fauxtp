"""Pattern matching helpers for receive()."""

from typing import Any


class _Any:
    """Matches any value, extracts it."""
    def __repr__(self): return "ANY"


ANY = _Any()


class _Ignore:
    """Matches any value, does not extract."""
    def __repr__(self): return "_"


IGNORE = _ = _Ignore()


def match_pattern(value: Any, pattern: Any) -> tuple[Any, ...] | None:
    """
    Match a value against a pattern, returning extracted values.
    
    Examples:
        match_pattern(("ping", 123), ("ping", ANY)) 
        # → (123,)
        
        match_pattern(("data", "json", {...}), ("data", str, dict))
        # → ("json", {...})
        
        match_pattern("hello", str)
        # → ("hello",)
    """
    match pattern:
        case _Any():
            return (value,)
        case _Ignore():
            return ()
        case type() as t if isinstance(value, t):
            return (value,)
        case tuple() as pat if isinstance(value, tuple) and len(value) == len(pat):
            extracted = []
            for v, p in zip(value, pat):
                if (sub := match_pattern(v, p)) is None:
                    return None
                extracted.extend(sub)
            return tuple(extracted)
        case x if x == value:
            return ()
        case _:
            return None