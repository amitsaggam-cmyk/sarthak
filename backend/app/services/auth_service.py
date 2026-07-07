from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password

from app.core.security import (
    create_access_token,
    verify_password,
)
from app.db.models import User


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> User | None:
    """Fetch a user by email."""

    result = await db.execute(
        select(User).where(User.email == email)
    )

    return result.scalar_one_or_none()

async def create_user(
    db: AsyncSession,
    full_name: str,
    email: str,
    password: str,
) -> User:
    """Create a new user."""
    existing_user = await get_user_by_email(
        db,
        email,
    )
    if existing_user:
        raise ValueError("User already exists")
    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[User | None, str | None]:
    """
    Authenticate a user.
    Returns:
        (user, access_token)
    """

    user = await get_user_by_email(
        db,
        email,
    )

    if user is None:
        return None, None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None, None

    token = create_access_token(
        subject=user.email,
    )

    return user, token