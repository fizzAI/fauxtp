from typing_extensions import override
from .generic import FauxStorage, T, U

from rpds import HashTrieMap

class RPDSFauxStorage(FauxStorage[T, U]):
    """
    A [`FauxStorage`] backed by RPDS data structures.
    """

    _backing: "HashTrieMap[T,U]"

    def __init__(self, backing: "HashTrieMap[T,U]" = HashTrieMap()):  # pyright: ignore[reportCallInDefaultInitializer]
        self._backing = backing

    @override
    def get(self, key: T) -> U:
        return self._backing[key]
    
    @override
    def set(self, key: T, val: U) -> "RPDSFauxStorage[T,U]":
        return RPDSFauxStorage(self._backing.insert(key, val))
    
    @override
    def delete(self, key: T) -> "RPDSFauxStorage[T,U]":
        return RPDSFauxStorage(self._backing.discard(key))
    
    @override
    def __contains__(self, key: T) -> bool:
        return self._backing.__contains__(key)