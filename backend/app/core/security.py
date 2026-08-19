from datetime import datetime, timedelta, timezone

import jwt
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings



settings = get_settings()
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )
    
def create_access_token(
    subject: str,
) -> str:
    expire = datetime.now(
        timezone.utc
    ) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": subject,
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    subject: str,
) -> str:
    expire = datetime.now(
        timezone.utc
    ) + timedelta(
        minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_password_reset_token(
    subject: str,
) -> str:
    expire = datetime.now(
        timezone.utc
    ) + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": subject,
        "purpose": "password_reset",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_password_reset_token(
    token: str,
) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except InvalidTokenError:
        return None

    if payload.get("purpose") != "password_reset":
        return None

    return payload.get("sub")


def decode_access_token(
    token: str,
) -> dict:

    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def decode_refresh_token(
    token: str,
) -> dict:

    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
