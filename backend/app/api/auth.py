from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.models import User
from app.models.auth import UserResponse
from app.db.session import get_session
from fastapi.security import OAuth2PasswordRequestForm
from app.models.auth import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
)
from app.services.auth_service import (
    create_user,
    authenticate_user,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    request: SignupRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        await create_user(
            session,
            request.full_name,
            request.email,
            request.password,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "message": "User created successfully"
    }

@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    user, token = await authenticate_user(
        session,
        form_data.username,  # User enters email here
        form_data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return TokenResponse(
        access_token=token,
    )
    
@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user