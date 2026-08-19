from datetime import datetime, timedelta
import json
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.db.models import User, UserManagementAudit

MODULE_ACCESS_OPTIONS = ("background_verification", "document_verification")

def normalize_module_access(role: str, module_access: dict[str, str] | None) -> dict[str, str]:
    """Return canonical module access for a role."""
    if role == "admin":
        return {mod: "write" for mod in MODULE_ACCESS_OPTIONS}
    
    allowed = set(MODULE_ACCESS_OPTIONS)
    normalized: dict[str, str] = {}
    
    for module, level in (module_access or {}).items():
        if module in allowed and level in ("read", "write"):
            normalized[module] = level
            
    return normalized

def module_access_label(module: str) -> str:
    labels = {
        "background_verification": "Background Verification",
        "document_verification": "Document Verification",
    }
    return labels.get(module, module)


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> User | None:
    """Fetch a user by email."""
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def count_users(db: AsyncSession) -> int:
    """Count total users in the system (used to detect first-time bootstrap)."""
    result = await db.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def list_users(db: AsyncSession) -> list[User]:
    """Return all users, ordered by id."""
    result = await db.execute(select(User).order_by(User.id))
    return list(result.scalars().all())


async def create_user(
    db: AsyncSession,
    full_name: str,
    email: str,
    password: str,
    role: str = "user",
    module_access: dict[str, str] | None = None,
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
        role=role,
        module_access_json=json.dumps(normalize_module_access(role, module_access)),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(
    db: AsyncSession,
    user_id: int,
) -> User | None:
    """Fetch a user by id."""
    return await db.get(User, user_id)


async def update_user(
    db: AsyncSession,
    user: User,
    role: str | None = None,
    is_active: bool | None = None,
    module_access: dict[str, str] | None = None,
) -> User:
    """Update a user's role and/or active status."""
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active

    if role is not None or module_access is not None:
        user.module_access_json = json.dumps(
            normalize_module_access(user.role, module_access if module_access is not None else user.module_access)
        )

    await db.commit()
    await db.refresh(user)
    return user


async def create_user_management_audit(
    db: AsyncSession,
    actor: User | None,
    target: User,
    action: str,
    before: dict | None,
    after: dict,
    status_value: str = "SUCCESS",
) -> UserManagementAudit:
    """Store a user-management audit event."""
    audit = UserManagementAudit(
        actor_user_id=actor.id if actor else None,
        target_user_id=target.id,
        action=action,
        status=status_value,
        details_json=json.dumps(
            {
                "targetUserName": target.full_name,
                "targetEmail": target.email,
                "assignedRole": after.get("role", target.role),
                "actionType": action,
                "clientIpAddress": "Not captured",
                "geographicLocation": "Not captured",
                "browserUserAgent": "Not captured",
                "stateChange": {
                    "before": before,
                    "after": after,
                },
            },
            default=str,
        ),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


def user_state(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "module_access": user.module_access,
    }


def describe_user_update(before: dict, after: dict) -> str:
    actions: list[str] = []
    
    before_modules = before.get("module_access") or {}
    after_modules = after.get("module_access") or {}

    granted = []
    changed = []
    revoked = []

    for module, level in after_modules.items():
        if module not in before_modules:
            granted.append(f"{module_access_label(module)} ({level})")
        elif before_modules[module] != level:
            changed.append(f"{module_access_label(module)} ({before_modules[module]} to {level})")

    for module in before_modules:
        if module not in after_modules:
            revoked.append(module_access_label(module))

    if before.get("role") != after.get("role"):
        actions.append(f"Role updated (to {after.get('role')})")
        
    if before.get("is_active") != after.get("is_active"):
        status = "Active" if after.get("is_active") else "Inactive"
        actions.append(f"Status updated (to {status})")

    if granted:
        actions.append("Access granted: " + ", ".join(sorted(granted)))
    if changed:
        actions.append("Access modified: " + ", ".join(sorted(changed)))
    if revoked:
        actions.append("Access revoked: " + ", ".join(sorted(revoked)))

    return "; ".join(actions) or "User account updated"


def generate_password_reset_pin() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


async def set_password_reset_pin(
    db: AsyncSession,
    user: User,
    pin: str,
    expires_at: datetime,
) -> User:
    user.password_reset_pin_hash = hash_password(pin)
    user.password_reset_pin_expires_at = expires_at
    await db.commit()
    await db.refresh(user)
    return user


async def verify_password_reset_pin(
    user: User,
    pin: str,
) -> bool:
    if not user.password_reset_pin_hash or not user.password_reset_pin_expires_at:
        return False
    if user.password_reset_pin_expires_at < datetime.utcnow():
        return False
    return verify_password(pin, user.password_reset_pin_hash)


async def clear_password_reset_pin(
    db: AsyncSession,
    user: User,
) -> User:
    user.password_reset_pin_hash = None
    user.password_reset_pin_expires_at = None
    await db.commit()
    await db.refresh(user)
    return user


async def update_password(
    db: AsyncSession,
    user: User,
    new_password: str,
) -> User:
    """Update a user's password hash."""
    user.password_hash = hash_password(new_password)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(
    db: AsyncSession,
    user: User,
) -> None:
    """Permanently delete a user."""
    await db.delete(user)
    await db.commit()


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[User | None, str | None, str | None]:
    """
    Authenticate a user.
    Returns:
        (user, access_token, refresh_token)
    """
    user = await get_user_by_email(
        db,
        email,
    )
    if user is None:
        return None, None, None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None, None, None

    access_token = create_access_token(
        subject=user.email,
    )
    refresh_token = create_refresh_token(
        subject=user.email,
    )
    return user, access_token, refresh_token