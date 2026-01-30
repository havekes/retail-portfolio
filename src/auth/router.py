from typing import Annotated

from fastapi import APIRouter

from src.auth.api import UserApi, user_api_factory
from src.auth.api_types import AuthResponse, LoginRequest, SignupRequest

auth_router = APIRouter(prefix="/api/auth")


@auth_router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignupRequest,
    user_service: Annotated[UserApi, user_api_factory],
) -> AuthResponse:
    return await user_service.signup(request.email, request.password)


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    user_service: Annotated[UserApi, user_api_factory],
) -> AuthResponse:
    return await user_service.login(request.email, request.password)
