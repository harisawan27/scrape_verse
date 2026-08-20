"""Neon Auth (Managed Better Auth) session verification and user resolution for Web Radar."""

import logging
from typing import Any
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

logger = logging.getLogger("webradar.auth")

# In-memory test session store for mock / SQLite unit test execution
_TEST_SESSIONS: dict[str, dict[str, str]] = {}


def register_test_session(token: str, user_id: str, email: str) -> None:
    """Register a test session for test suite and mock execution."""
    _TEST_SESSIONS[token] = {"user_id": user_id, "email": email}


def clear_test_sessions() -> None:
    """Clear registered test sessions."""
    _TEST_SESSIONS.clear()


def verify_neon_session(token: str, db: Session) -> tuple[str, str] | None:
    """Verify session token against Neon Auth managed schema (neon_auth.session).
    
    Returns (neon_user_id, email) if valid and not expired, else None.
    """
    # 1. Check test sessions registry first (for unit tests / mock mode)
    if token in _TEST_SESSIONS:
        info = _TEST_SESSIONS[token]
        return info["user_id"], info["email"]

    # 2. Query Neon Auth tables in PostgreSQL
    try:
        query = text("""
            SELECT s."userId"::text AS neon_user_id, u.email AS email
            FROM neon_auth.session s
            JOIN neon_auth.user u ON s."userId" = u.id
            WHERE s.token = :token
              AND s."expiresAt" > CURRENT_TIMESTAMP
            LIMIT 1;
        """)
        row = db.execute(query, {"token": token}).first()
        if row:
            return str(row.neon_user_id), str(row.email)
    except (OperationalError, ProgrammingError) as err:
        # If neon_auth schema does not exist (e.g. temporary SQLite in memory tests)
        logger.debug("Neon Auth table query failed (likely SQLite test env): %s", err)
        pass
    except Exception as exc:
        logger.warning("Error verifying Neon Auth session: %s", exc)

    return None


def resolve_or_create_user(db: Session, auth_id: str, email: str) -> User:
    """Resolve an existing domain User profile by auth_id or email, or provision one."""
    user = db.query(User).filter(
        (User.auth_id == auth_id) | (User.id == auth_id) | (User.email == email)
    ).first()

    if user is None:
        user = User(
            email=email,
            auth_id=auth_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created domain user profile %s for Neon Auth user %s (%s)", user.id, auth_id, email)
    elif not user.auth_id:
        user.auth_id = auth_id
        db.commit()
        db.refresh(user)

    return user


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias="better-auth.session_token"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    """Enforce managed Neon Auth authentication on protected routes.
    
    Verifies token against neon_auth.session, or resolves test headers.
    """
    token: str | None = None

    # 1. Bearer Token
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()

    # 2. Session Cookie fallback
    if not token and session_cookie:
        token = session_cookie.strip()

    if token:
        neon_auth_info = verify_neon_session(token, db)
        if neon_auth_info:
            neon_user_id, email = neon_auth_info
            return resolve_or_create_user(db, auth_id=neon_user_id, email=email)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Neon Auth session",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 3. Test Fixture Fallback (X-User-Id header for mock test suites)
    if x_user_id:
        user = db.get(User, x_user_id.strip())
        if user is None:
            # Check by auth_id
            user = db.query(User).filter(User.auth_id == x_user_id.strip()).first()
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test user not found",
        )

    # 4. Unauthenticated
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_optional_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias="better-auth.session_token"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User | None:
    """Optional authentication resolver that returns None rather than raising 401."""
    try:
        return get_current_user(
            request=request,
            authorization=authorization,
            session_cookie=session_cookie,
            x_user_id=x_user_id,
            db=db,
        )
    except HTTPException:
        return None
