from typing import Annotated, Sequence
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.office_auth import OfficeUser, OfficeRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OfficeUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        if not isinstance(payload, dict):
            raise credentials_exception

        # Guard: Check token type only if present in the claim
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            raise credentials_exception

        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise credentials_exception

        user_id = UUID(str(user_id_str))
    except (JWTError, ValueError, Exception):
        raise credentials_exception

    stmt = (
        select(OfficeUser)
        .options(selectinload(OfficeUser.employee_profile))
        .where(OfficeUser.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception

    if not user.is_active or user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or locked.",
        )

    return user


def require_roles(allowed_roles: Sequence[OfficeRole | str]):
    # Normalize allowed roles to string values for bulletproof matching
    normalized_allowed = {
        role.value if isinstance(role, OfficeRole) else str(role)
        for role in allowed_roles
    }
    super_admin_val = OfficeRole.SUPER_ADMIN.value

    def role_checker(
        current_user: Annotated[OfficeUser, Depends(get_current_user)],
    ) -> OfficeUser:
        user_role_str = (
            current_user.role.value
            if isinstance(current_user.role, OfficeRole)
            else str(current_user.role)
        )

        # SUPER_ADMIN retains platform-wide clearance
        if user_role_str == super_admin_val:
            return current_user

        if user_role_str not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action prohibited for role: {user_role_str}",
            )

        return current_user

    return role_checker