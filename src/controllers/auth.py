from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.repositories.sqlalchemy.sqlalchemy_user import SqlAlchemyUserRepository
from src.schemas.auth import AuthResponse, LoginRequest, SignupRequest
from src.services.auth import AuthService

router = APIRouter()

def get_auth_service(
    session: AsyncSession = Depends(get_db_session)
    ) -> AuthService:
    user_repo = SqlAlchemyUserRepository(session)
    return AuthService(user_repo)

@router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignupRequest,
    service: AuthService = Depends(get_auth_service)
    ):
    return await service.signup(request.email, request.password)

@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
     service: AuthService = Depends(get_auth_service)
     ):
    return await service.login(request.email, request.password)
