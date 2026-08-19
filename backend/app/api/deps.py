from fastapi import Depends, HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, oauth2_scheme
from app.db.models import User
from app.db.session import get_session
from app.services.auth_service import get_user_by_email


def user_has_module_access(user: User, module: str) -> bool:
    return user.role == "admin" or module in user.module_access


def require_module_access(module: str):
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not user_has_module_access(current_user, module):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this module.",
            )
        return current_user

    return dependency


def require_module_write_access(module: str):
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != "admin" and current_user.module_access.get(module) != "write":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Write access to this module is required.",
            )
        return current_user

    return dependency


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        payload = decode_access_token(token)
        email = payload.get("sub")

        if email is None or payload.get("type") not in {None, "access"}:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    user = await get_user_by_email(
        session,
        email,
    )
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user
