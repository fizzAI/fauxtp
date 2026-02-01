from typing import Any

from .generic import FauxStorage

try:
    from .rpds import RPDSFauxStorage as _DefaultFauxStorage
except ImportError:
    from .dict import DictFauxStorage as _DefaultFauxStorage

# `TypeVar`s like `T`/`U` are only meaningful in a generic function/class scope, so we
# intentionally erase them here and expose a type-safe base class.
DEFAULT_FAUXSTORAGE = _DefaultFauxStorage

__all__ = ["FauxStorage", "DEFAULT_FAUXSTORAGE"]