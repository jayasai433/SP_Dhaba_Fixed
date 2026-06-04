from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field

class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Literal["admin", "staff", "viewer"]
    is_active: bool
    created_at: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class UserCreateIn(BaseModel):
    name:     str = Field(min_length=1, max_length=100)
    email:    EmailStr
    password: str = Field(min_length=8, max_length=128)
    role:     Literal["admin", "staff", "viewer"]

class UserUpdateIn(BaseModel):
    name:      Optional[str]                              = None
    role:      Optional[Literal["admin", "staff", "viewer"]] = None
    is_active: Optional[bool]                             = None

class PasswordResetIn(BaseModel):
    new_password: str
