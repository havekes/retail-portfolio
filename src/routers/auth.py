from fastapi import APIRouter
from svcs.fastapi import DepContainer

from src.schemas.auth import AuthResponse, LoginRequest, SignupRequest
from src.services.auth import AuthService

router = APIRouter(prefix="/api/auth")


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest, services: DepContainer):
    auth_service = await services.aget(AuthService)

    return await auth_service.signup(request.email, request.password)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, services: DepContainer):
    auth_service = await services.aget(AuthService)

    return await auth_service.login(request.email, request.password)
