import bcrypt
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt
from app.core.config import settings

def hash_password(password: str) -> str:
    # Native bcrypt handling safe from the 72-byte overflow bug
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

def hash_token(token: str) -> str:
    """Produces SHA-256 digest of refresh token before persisting to database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_access_token(subject: str, role: str, additional_claims: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "type": "access"
    }
    if additional_claims:
        payload.update(additional_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])