import logging
from datetime import datetime, timezone, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    hash_token,
)
from app.models.office_auth import OfficeUser, OfficeUserSession
from app.schemas.office_auth import (
    TokenResponse,
    UserAuthResponse,
    PasswordChangeRequest,
)
from app.dependencies.office_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Office Authentication & RBAC"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends(OAuth2PasswordRequestForm)],
):
    try:
        # 1. Fetch user by lowercase email
        clean_email = form_data.username.strip().lower()
        stmt = (
            select(OfficeUser)
            .options(selectinload(OfficeUser.employee_profile))
            .where(OfficeUser.email == clean_email)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        # 2. Check credentials & password hash
        if not user or not verify_password(form_data.password, user.password_hash):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.is_locked = True
                await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. Guard inactive or locked accounts
        if not user.is_active or user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive or locked by administrator.",
            )

        # 4. Reset failure tracking
        user.failed_login_attempts = 0
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # 5. Issue JWT tokens
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            additional_claims={"email": user.email},
        )
        refresh_token = create_refresh_token(subject=str(user.id))

        # 6. Parse Client IP safely without throwing AttributeError
        client_ip = "127.0.0.1"
        try:
            if request.headers.get("x-forwarded-for"):
                client_ip = request.headers.get("x-forwarded-for").split(",")[0].strip()
            elif request.client and hasattr(request.client, "host") and request.client.host:
                client_ip = request.client.host
        except Exception:
            client_ip = "127.0.0.1"

        user_agent = request.headers.get("user-agent", "Unknown")
        refresh_days = getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
        access_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)

        # 7. Persist session record inside a safe try/except block
        # Even if session tracking fails, the user will still successfully authenticate
        try:
            session_record = OfficeUserSession(
                user_id=user.id,
                refresh_token_hash=hash_token(refresh_token),
                ip_address=client_ip,
                user_agent=user_agent,
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(days=refresh_days),
            )
            db.add(session_record)
            await db.commit()
        except Exception as session_err:
            logger.error(f"[LOGIN_SESSION_WARN] Failed to write session audit: {session_err}")
            await db.rollback()
            # Still commit user's updated login timestamp
            user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()

        # 8. Set sliding session cookie
        is_dev = getattr(settings, "ENVIRONMENT", "development") == "development"
        response.set_cookie(
            key="bacchus_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=(not is_dev),
            samesite="lax",
            max_age=refresh_days * 86400,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": access_minutes * 60,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[CRITICAL_LOGIN_ERROR] Unhandled login failure: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login process error: {str(exc)}",
        )


@router.get("/me", response_model=UserAuthResponse)
async def get_my_context(current_user: Annotated[OfficeUser, Depends(get_current_user)]):
    return current_user


@router.post("/change-password")
async def change_password(
    payload: PasswordChangeRequest,
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )

    current_user.password_hash = hash_password(payload.new_password)

    # Invalidate all active user sessions
    stmt = select(OfficeUserSession).where(
        OfficeUserSession.user_id == current_user.id,
        OfficeUserSession.revoked.is_(False),
    )
    sessions = (await db.execute(stmt)).scalars().all()
    for s in sessions:
        s.revoked = True

    await db.commit()
    return {"message": "Password updated successfully. All other sessions have been terminated."}