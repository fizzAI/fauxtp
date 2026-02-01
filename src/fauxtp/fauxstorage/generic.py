# pyright: reportUnusedParameter=false
from typing import Generic, TypeVar

T = TypeVar('T')
U = TypeVar('U')

class FauxStorage(Generic[T,U]):
    """
    FauxStorage

    Formalized(ish) semantics around an immutable dict/hashmap and how they should be used for state and other table-like structures.
    Only a one to one mapping, ie each key has one value
    """

    def get(self, key: T) -> U:
        ...

    def set(self, key: T, val: U) -> "FauxStorage[T,U]":
        ...

    def delete(self, key: T) -> "FauxStorage[T,U]":
        ...

    def __contains__(self, key: T) -> bool:
        try:
            _ = self.get(key)
            return True
        except Exception:
            return False