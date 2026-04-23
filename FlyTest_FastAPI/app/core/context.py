from contextvars import ContextVar
from uuid import uuid4


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def ensure_request_id() -> str:
    value = request_id_ctx.get()
    if value:
        return value
    value = uuid4().hex
    request_id_ctx.set(value)
    return value
