# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from typing import Any

from maasservicelayer.models.tokens import (
    OIDCRevokedToken,
    RefreshToken,
    Token,
)
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_user_token(
    fixture: Fixture, user_id: int, consumer_id: int, **extra_details: Any
) -> Token:
    token = {
        "key": "CtE9Cmy4asnRBtJvxQ",
        "secret": "DNPJDVa87vEesHE8sQ722yP6JJKnrem2",
        "verifier": "",
        "token_type": 2,
        "timestamp": 1725122700,
        "is_approved": True,
        "callback_confirmed": False,
        "consumer_id": consumer_id,
        "user_id": user_id,
    }

    [created_token] = await fixture.create("piston3_token", [token])
    return Token(**created_token)


async def create_test_refresh_token(
    fixture: Fixture,
    **extra_details: Any,
) -> RefreshToken:
    now = utcnow()
    refresh_token = {
        "expires_at": now + timedelta(days=1),
        "token": "refresh_token_abc123",
        "user_id": 1,
        "created": now,
        "updated": now,
    }

    refresh_token.update(extra_details)
    [created_refresh_token] = await fixture.create(
        "maasserver_refreshtoken", [refresh_token]
    )
    return RefreshToken(**created_refresh_token)


async def create_test_revoked_token(
    fixture: Fixture, **extra_details: Any
) -> OIDCRevokedToken:
    revoked_token = {
        "token_hash": "abc123",
        "revoked_at": utcnow(),
        "user_email": "test@abc.com",
        "provider_id": 1,
    }
    revoked_token.update(extra_details)
    [created_revoked_token] = await fixture.create(
        "maasserver_oidcrevokedtoken", [revoked_token]
    )
    return OIDCRevokedToken(**created_revoked_token)
