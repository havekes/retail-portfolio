import os
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status

from src.repositories.sqlalchemy.sqlalchemy_user import SqlAlchemyUserRepository

if TYPE_CHECKING:
    from src.schemas.user import User

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class AuthService:
    def __init__(self, user_repository: SqlAlchemyUserRepository):
        self.user_repository = user_repository

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def hash_password(self, password: str) -> str:
        password_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        expire = datetime.now(UTC) + (
            expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    async def signup(self, email: str, password: str) -> dict:
        existing_user = await self.user_repository.get_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        hashed_password = self.hash_password(password)
        user = await self.user_repository.create_user(email, hashed_password)

        access_token = self.create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer", "user": user}

    async def login(self, email: str, password: str) -> dict:
        user = await self.user_repository.get_by_email(email)
        if not user or not self.verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        access_token = self.create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer", "user": user}
