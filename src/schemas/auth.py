from pydantic import BaseModel, EmailStr
<<<<<<< HEAD

from src.schemas.user import User

DEFAULT_TOKEN_TYPE = "bearer"

<<<<<<< HEAD

=======
>>>>>>> 8c1903d (fix pipeline)
=======
from src.schemas.user import User

>>>>>>> c45126e (finish login)
class SignupRequest(BaseModel):
    email: EmailStr
    password: str

<<<<<<< HEAD

=======
>>>>>>> c45126e (finish login)
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

<<<<<<< HEAD

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = DEFAULT_TOKEN_TYPE
    user: User
=======
class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
>>>>>>> c45126e (finish login)
