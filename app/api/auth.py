import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    unauthorized,
    verify_password,
)
from app.db.database import Database, get_db
from app.schemas.business import TokenResponse

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post(
    "/token",
    response_model=TokenResponse,
)
async def login(
    request: Request,
    form: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
    db: Annotated[
        Database,
        Depends(get_db),
    ],
):

    if len(form.password) > 256:
        raise unauthorized()

    customer_id = form.username.strip().upper()

    customer = await db.fetch_one(
        """
        SELECT customer_id, password_hash, enabled
        FROM customers
        WHERE customer_id = ?
        """,
        (customer_id,),
    )

    stored_hash = (
        customer["password_hash"]
        if customer
        else DUMMY_PASSWORD_HASH
    )

    valid = await asyncio.to_thread(
        verify_password,
        form.password,
        stored_hash,
    )

    if not customer or not valid or not customer["enabled"]:
        raise unauthorized()

    settings = request.app.state.settings

    token = create_access_token(
        customer["customer_id"],
        settings,
    )

    return TokenResponse(
        access_token=token,
        expires_in=(
            settings.access_token_expire_minutes * 60
        ),
    )