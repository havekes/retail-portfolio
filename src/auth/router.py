from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.auth.api import UserApi, user_api_factory
from src.auth.api_types import AuthResponse, LoginRequest, SignupRequest
from src.auth.exceptions import AuthInvalidCredentialsError, AuthUserAlreadyExistsError

auth_router = APIRouter(prefix="/api/auth")


@auth_router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignupRequest,
    user_service: Annotated[UserApi, Depends(user_api_factory)],
) -> AuthResponse:
    try:
        return await user_service.signup(request.email, request.password)
    except AuthUserAlreadyExistsError as e:
        raise HTTPException(409, "User with email already exists") from e


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    user_service: Annotated[UserApi, Depends(user_api_factory)],
) -> AuthResponse:
    try:
        return await user_service.login(request.email, request.password)
    except AuthInvalidCredentialsError as e:
        raise HTTPException(401, "Invalid credentials") from e
