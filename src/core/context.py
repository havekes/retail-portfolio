from contextvars import ContextVar, Token

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Retrieve the current correlation/request ID for the context."""
    return request_id_ctx_var.get()


def set_request_id(request_id: str | None) -> Token[str | None]:
    """Set the correlation/request ID for the current context."""
    return request_id_ctx_var.set(request_id)
