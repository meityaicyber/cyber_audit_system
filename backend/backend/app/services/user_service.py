import uuid
from typing import Optional, List

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, Role, UserRole
from app.utils.security import hash_password


async def get_users(
    db: AsyncSession, skip: int = 0, limit: int = 50
) -> tuple[List[User], int]:
    """Get paginated list of users with roles."""
    # Count total
    count_result = await db.execute(select(func.count(User.user_id)))
    total = count_result.scalar()

    # Fetch users
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().unique().all()

    return users, total


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Get a single user by ID."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    role_names: List[str] = None,
) -> User:
    """Create a new user with specified roles."""
    # Check existing
    existing = await db.execute(
        select(User).where((User.username == username) | (User.email == email))
    )
    if existing.scalar_one_or_none():
        raise ValueError("Username or email already exists")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Assign roles
    if role_names:
        for role_name in role_names:
            role_result = await db.execute(
                select(Role).where(Role.role_name == role_name)
            )
            role = role_result.scalar_one_or_none()
            if role:
                user_role = UserRole(user_id=user.user_id, role_id=role.role_id)
                db.add(user_role)

    await db.flush()

    # Reload with roles
    return await get_user_by_id(db, user.user_id)


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    role_names: Optional[List[str]] = None,
) -> Optional[User]:
    """Update an existing user."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    if email is not None:
        # Check email uniqueness
        existing = await db.execute(
            select(User).where(User.email == email, User.user_id != user_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Email already exists")
        user.email = email

    if full_name is not None:
        user.full_name = full_name

    if is_active is not None:
        user.is_active = is_active

    if role_names is not None:
        # Remove existing roles
        await db.execute(
            delete(UserRole).where(UserRole.user_id == user_id)
        )
        # Add new roles
        for role_name in role_names:
            role_result = await db.execute(
                select(Role).where(Role.role_name == role_name)
            )
            role = role_result.scalar_one_or_none()
            if role:
                user_role = UserRole(user_id=user_id, role_id=role.role_id)
                db.add(user_role)

    await db.flush()
    return await get_user_by_id(db, user_id)


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Deactivate a user (soft delete)."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return False
    user.is_active = False
    await db.flush()
    return True
