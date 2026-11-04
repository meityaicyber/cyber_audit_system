import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, Role, UserRole, UserSession
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from app.config import settings


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[User]:
    """Authenticate a user by username and password."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.username == username, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, str(user.password_hash)):
        return None

    # Update last login
    user.last_login = datetime.now(timezone.utc)  # type: ignore
    await db.flush()
    return user


async def create_session(
    db: AsyncSession,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Create a new session with access and refresh tokens."""
    role_names = [ur.role.role_name for ur in user.roles] if user.roles else []

    session_id = str(uuid.uuid4())

    access_token = create_access_token(
        data={"sub": str(user.user_id), "roles": role_names}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.user_id), "session_id": session_id, "roles": role_names}
    )

    # Store session
    session = UserSession(
        session_id=uuid.UUID(session_id),
        user_id=user.user_id,
        refresh_token_hash=hash_token(refresh_token),
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def refresh_session(db: AsyncSession, refresh_token: str) -> Optional[dict]:
    """Refresh a session and rotate the refresh token."""
    try:
        payload = decode_token(refresh_token)
    except Exception:
        return None

    if payload.get("type") != "refresh":
        return None

    session_id = payload.get("session_id")
    user_id = payload.get("sub")

    if not session_id or not user_id:
        return None

    # Verify session exists
    result = await db.execute(
        select(UserSession).where(
            UserSession.session_id == uuid.UUID(session_id),
            UserSession.user_id == uuid.UUID(user_id),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return None

    # Check expiry
    if session.expires_at < datetime.now(timezone.utc):
        await db.delete(session)
        await db.flush()
        return None

    # Verify token hash
    if session.refresh_token_hash != hash_token(refresh_token):
        # Token reuse detected - invalidate session
        await db.delete(session)
        await db.flush()
        return None

    # Load user with roles
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.user_id == uuid.UUID(user_id))
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        return None

    role_names = [ur.role.role_name for ur in user.roles] if user.roles else []

    # Create new tokens
    new_access_token = create_access_token(
        data={"sub": str(user.user_id), "roles": role_names}
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.user_id), "session_id": session_id, "roles": role_names}
    )

    # Update session with new refresh token hash
    session.refresh_token_hash = hash_token(new_refresh_token)  # type: ignore
    session.expires_at = datetime.now(timezone.utc) + timedelta(  # type: ignore
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    await db.flush()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


async def revoke_session(
    db: AsyncSession, user_id: uuid.UUID, session_id: Optional[str] = None
) -> bool:
    """Revoke a specific session or all sessions for a user."""
    if session_id:
        result = await db.execute(
            delete(UserSession).where(
                UserSession.session_id == uuid.UUID(session_id),
                UserSession.user_id == user_id,
            )
        )
    else:
        result = await db.execute(
            delete(UserSession).where(UserSession.user_id == user_id)
        )
    await db.flush()
    return result.rowcount > 0


async def seed_roles_and_admin(db: AsyncSession):
    """Seed default roles and admin user on first startup."""
    # Create roles if they don't exist
    role_names = ["ADMIN", "AUDITOR", "REVIEWER"]
    existing_roles = await db.execute(select(Role))
    existing_role_names = {r.role_name for r in existing_roles.scalars().all()}

    roles_map = {}
    for role_name in role_names:
        if role_name not in existing_role_names:
            role = Role(
                role_name=role_name,
                description=f"{role_name.title()} role for the system",
            )
            db.add(role)
            await db.flush()
            roles_map[role_name] = role
        else:
            result = await db.execute(
                select(Role).where(Role.role_name == role_name)
            )
            roles_map[role_name] = result.scalar_one()

    # Create admin user if doesn't exist
    admin_result = await db.execute(
        select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
    )
    admin_user = admin_result.scalar_one_or_none()

    if not admin_user:
        admin_user = User(
            username=settings.DEFAULT_ADMIN_USERNAME,
            email=settings.DEFAULT_ADMIN_EMAIL,
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            full_name="System Administrator",
            is_active=True,
        )
        db.add(admin_user)
        await db.flush()

        # Assign ADMIN role
        user_role = UserRole(
            user_id=admin_user.user_id,  # type: ignore
            role_id=roles_map["ADMIN"].role_id,  # type: ignore
        )
        db.add(user_role)
        await db.flush()

    await db.commit()
