from typing import Literal
from pydantic import BaseModel, EmailStr, Field

# Define specific access levels and available modules
AccessLevel = Literal["read", "write"]
ModuleAccess = Literal["background_verification", "document_verification"]

class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: Literal["admin", "user"] = "user"
    # Updated to accept a dictionary of module permissions
    module_access: dict[ModuleAccess, AccessLevel] = Field(default_factory=dict)

class UserUpdateRequest(BaseModel):
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None
    # Updated to accept a dictionary of module permissions
    module_access: dict[ModuleAccess, AccessLevel] | None = None

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    pin: str
    new_password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    role: str
    # Updated to return a dictionary of module permissions
    module_access: dict[str, str] = Field(default_factory=dict)

    model_config = {
        "from_attributes": True,
    }