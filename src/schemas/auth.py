from pydantic import BaseModel, EmailStr

from src.schemas.user import User

DEFAULT_TOKEN_TYPE = "bearer"

<<<<<<< HEAD

=======
>>>>>>> 8c1903d (fix pipeline)
class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = DEFAULT_TOKEN_TYPE
    user: User
