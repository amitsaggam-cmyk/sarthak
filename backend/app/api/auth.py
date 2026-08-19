from datetime import datetime, timedelta

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
    RefreshTokenRequest,
    TokenResponse,
    UserUpdateRequest,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
)
from app.services.auth_service import (
    create_user,
    authenticate_user,
    count_users,
    list_users,
    get_user_by_email,
    get_user_by_id,
    generate_password_reset_pin,
    set_password_reset_pin,
    verify_password_reset_pin,
    clear_password_reset_pin,
    update_user,
    delete_user,
    update_password,
    create_user_management_audit,
    describe_user_update,
    normalize_module_access,
    user_state,
)
from app.services.smtp_client import send_password_reset_email
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token
from jwt.exceptions import InvalidTokenError

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
    existing_count = await count_users(session)

    if existing_count == 0:
        # Bootstrap: the very first account in the system becomes admin.
        role = "admin"
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signup is disabled. Ask an admin to create your account.",
        )

    try:
        await create_user(
            session,
            request.full_name,
            request.email,
            request.password,
            role,
            normalize_module_access(role, request.module_access),
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
    "/users",
    status_code=status.HTTP_201_CREATED,
)
async def create_user_by_admin(
    request: SignupRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    try:
        user = await create_user(
            session,
            request.full_name,
            request.email,
            request.password,
            request.role,
            request.module_access,
        )
        await create_user_management_audit(
            session,
            current_user,
            user,
            "USER_CREATE",
            None,
            user_state(user),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "message": "User created successfully"
    }


@router.get(
    "/users",
    response_model=list[UserResponse],
)
async def get_users(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return await list_users(session)


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
)
async def update_user_by_admin(
    user_id: int,
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role or status",
        )

    target_user = await get_user_by_id(session, user_id)

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    before = user_state(target_user)
    updated_user = await update_user(
        session,
        target_user,
        role=request.role,
        is_active=request.is_active,
        module_access=request.module_access,
    )
    after = user_state(updated_user)
    await create_user_management_audit(
        session,
        current_user,
        updated_user,
        describe_user_update(before, after),
        before,
        after,
    )
    return updated_user


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_user_by_admin(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    target_user = await get_user_by_id(session, user_id)

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await delete_user(session, target_user)

    return {"message": "User deleted successfully"}

@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    user, access_token, refresh_token = await authenticate_user(
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
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
async def refresh_token(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not refresh credentials",
    )

    try:
        payload = decode_refresh_token(request.refresh_token)
        email = payload.get("sub")

        if email is None or payload.get("type") != "refresh":
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    user = await get_user_by_email(session, email)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
    )
    

@router.post(
    "/password-reset-request",
    status_code=status.HTTP_200_OK,
)
async def password_reset_request(
    request: PasswordResetRequest,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_email(session, request.email)

    if user:
        pin = generate_password_reset_pin()
        expires_at = datetime.utcnow() + timedelta(minutes=30)
        await set_password_reset_pin(session, user, pin, expires_at)
        settings = get_settings()
        reset_url = f"{settings.app_base_url}/reset-password"
        await send_password_reset_email(user.email, pin, reset_url)

    return {
        "message": "If that email exists, password reset instructions have been sent."
    }


@router.post(
    "/password-reset",
    status_code=status.HTTP_200_OK,
)
async def password_reset_confirm(
    request: PasswordResetConfirmRequest,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_email(session, request.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if not await verify_password_reset_pin(user, request.pin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset PIN.",
        )

    await update_password(session, user, request.new_password)
    await clear_password_reset_pin(session, user)
    return {
        "message": "Password updated successfully."
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user
