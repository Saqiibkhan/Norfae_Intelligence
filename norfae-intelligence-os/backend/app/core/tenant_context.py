from contextvars import ContextVar, Token
from contextlib import contextmanager
from collections.abc import Iterator


_current_business_id: ContextVar[int | None] = ContextVar(
    "norfae_current_business_id", default=None
)


def get_current_business_id() -> int | None:
    return _current_business_id.get()


def set_current_business_id(business_id: int) -> Token:
    if isinstance(business_id, bool) or business_id <= 0:
        raise ValueError("A positive business ID is required.")
    return _current_business_id.set(business_id)


def reset_current_business_id(token: Token) -> None:
    _current_business_id.reset(token)


@contextmanager
def tenant_scope(business_id: int) -> Iterator[None]:
    token = set_current_business_id(business_id)
    try:
        yield
    finally:
        reset_current_business_id(token)
