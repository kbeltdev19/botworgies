"""
Authentication module for Job Applier API.
Implements JWT-based authentication with secure token handling.
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


@dataclass
class User:
    """User model for authentication."""
    id: str
    email: str
    hashed_password: str
    created_at: datetime
    is_active: bool = True


@dataclass
class TokenPayload:
    """JWT token payload."""
    sub: str  # user_id
    exp: datetime
    type: str  # "access" or "refresh"


def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt."""
    salt = os.getenv("PASSWORD_SALT", "job-applier-salt")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(plain_password) == hashed_password


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a new JWT refresh token."""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"]),
            type=payload.get("type", "access")
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Dependency to get the current authenticated user.
    Returns user_id if authenticated, raises 401 otherwise.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload.sub


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Dependency to optionally get the current user.
    Returns user_id if authenticated, None otherwise.
    For endpoints that work both authenticated and anonymously.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def encrypt_sensitive_data(data: str) -> str:
    """
    Encrypt sensitive data (like LinkedIn cookies) for storage.
    Uses Fernet-like encryption with the secret key.
    """
    import base64
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    # Simple XOR encryption for now - in production use cryptography.fernet
    encrypted = bytes(a ^ b for a, b in zip(data.encode(), key * (len(data) // 32 + 1)))
    return base64.b64encode(encrypted).decode()


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    import base64
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    encrypted = base64.b64decode(encrypted_data.encode())
    decrypted = bytes(a ^ b for a, b in zip(encrypted, key * (len(encrypted) // 32 + 1)))
    return decrypted.decode()
