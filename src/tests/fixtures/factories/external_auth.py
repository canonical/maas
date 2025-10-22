#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from typing import Any

from maasservicelayer.models.external_auth import OAuthProvider, RootKey
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_rootkey(fixture: Fixture, **extra_details: Any) -> RootKey:
    created_at = utcnow()
    updated_at = utcnow()

    rootkey = {
        "created": created_at,
        "updated": updated_at,
        "expiration": created_at + timedelta(days=2),
    }
    rootkey.update(extra_details)

    [created_rootkey] = await fixture.create(
        "maasserver_rootkey",
        [rootkey],
    )
    return RootKey(**created_rootkey)


async def create_provider(
    fixture: Fixture, **extra_details: Any
) -> OAuthProvider:
    created_at = utcnow()
    updated_at = utcnow()

    provider = {
        "created": created_at,
        "updated": updated_at,
        "name": "test_provider",
        "client_id": "test_client_id",
        "client_secret": "test_secret",
        "issuer_url": "https://example.com",
        "redirect_uri": "https://example.com/callback",
        "scopes": "openid email profile",
        "enabled": True,
    }

    provider.update(extra_details)

    [created_provider] = await fixture.create(
        "maasserver_oidc_provider",
        [provider],
    )
    return OAuthProvider(**created_provider)
