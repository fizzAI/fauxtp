from collections.abc import Callable, Awaitable
from typing import Generic, TypeVar, TypeVarTuple, TypeAlias, Any

Ts = TypeVarTuple("Ts")
U = TypeVar("U")

class typed_lambda(Generic[*Ts]):
    def __new__(cls, f: Callable[[*Ts], U], /) -> Callable[[*Ts], U]:
        return f

MaybeAwaitableCallable: TypeAlias = Callable[..., Any] | Callable[..., Awaitable[Any]]