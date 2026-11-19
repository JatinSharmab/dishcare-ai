from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from app.config import Settings
from app.db.database import Database, get_db

password_hasher = PasswordHash.recommended()

DUMMY_PASSWORD_HASH = password_hasher.hash(
    "dummy-password-for-timing-check"
)

TOKEN_ISSUER = "dishcare-ai"
TOKEN_AUDIENCE = "dishcare-api"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    auto_error=False,
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(
    customer_id: str,
    settings: Settings,
) -> str:

    now = datetime.now(UTC)

    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": customer_id,
        "iat": now,
        "exp": expires_at,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Invalid or missing credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_customer(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Database, Depends(get_db)],
) -> str:

    return await authenticate_customer(token, request.app.state.settings, db)


async def authenticate_customer(token: str | None, settings: Settings, db: Database) -> str:
    if not token:
        raise unauthorized()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={
                "require": ["sub", "iat", "exp", "iss", "aud"]
            },
        )

        customer_id = payload["sub"]

        if not isinstance(customer_id, str):
            raise unauthorized()

    except jwt.InvalidTokenError:
        raise unauthorized() from None

    customer = await db.fetch_one(
        """
        SELECT customer_id, enabled
        FROM customers
        WHERE customer_id = ?
        """,
        (customer_id,),
    )

    if not customer or not customer["enabled"]:
        raise unauthorized()

    return customer_id


async def require_customer(
    customer_id: str,
    authenticated_customer: Annotated[
        str,
        Depends(get_current_customer),
    ],
) -> str:

    if customer_id != authenticated_customer:
        raise HTTPException(
            status_code=403,
            detail="Access to another customer is forbidden",
        )

    return authenticated_customer