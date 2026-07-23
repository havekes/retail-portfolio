import contextlib
import os

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config.settings import settings


def user_or_ip_key_func(request: Request) -> str:
    """Return user identifier from auth token if available, else fallback to IP."""
    token = request.cookies.get("auth_token") or request.headers.get("authorization")
    if token:
        token = token.removeprefix("Bearer ")
        with contextlib.suppress(Exception):
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("user_id") or payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        return token
    return get_remote_address(request)


is_test = os.getenv("ENVIRONMENT") == "test" or settings.environment == "test"
storage_uri = "memory://" if is_test else settings.redis_url

limiter = Limiter(
    key_func=user_or_ip_key_func,
    storage_uri=storage_uri,
    headers_enabled=True,
)
