from typing_extensions import override
from .generic import FauxStorage, T, U

import copy

class DictFauxStorage(FauxStorage[T, U]):
    """
    A [`FauxStorage`] backed by a regular Python dict and `copy.deepcopy()` for immutable ops.
    Warning, insertion may be O(N^D) where D is how deep the dict is packed if you use more mutable objects (like lists)
    """

    _backing: dict[T, U]

    def __init__(self, backing: dict[T,U] = {}):
        self._backing = backing

    @override
    def get(self, key: T) -> U:
        return self._backing[key]
    
    @override
    def set(self, key: T, val: U) -> "DictFauxStorage[T,U]":
        new_backing = copy.deepcopy(self._backing)
        new_backing[key] = val
        return DictFauxStorage(backing=new_backing)
    
    @override
    def delete(self, key: T) -> "DictFauxStorage[T,U]":
        new_backing = copy.deepcopy(self._backing)
        del new_backing[key]
        return DictFauxStorage(backing=new_backing)
    
    @override
    def __contains__(self, key: T) -> bool:
        return self._backing.__contains__(key)
