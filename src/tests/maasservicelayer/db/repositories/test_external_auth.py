#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.external_auth import OAuthProviderBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.external_auth import (
    ExternalOAuthRepository,
)
from maasservicelayer.db.tables import UserProfileTable
from maasservicelayer.models.external_auth import (
    AccessTokenType,
    OAuthProvider,
    ProviderMetadata,
    ProviderVendorType,
)
from tests.fixtures.factories.external_auth import create_provider
from tests.fixtures.factories.user import (
    create_test_user,
    create_test_user_profile,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestExternalOAuthRepository(RepositoryCommonTests[OAuthProvider]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[OAuthProvider]:
        return [
            await create_provider(
                fixture,
                name=f"provider_{i}",
                client_id=f"id_{i}",
                client_secret=f"provider_{i}_secret",
                issuer_url=f"https://provider-{i}.com/",
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ExternalOAuthRepository:
        return ExternalOAuthRepository(Context(connection=db_connection))

    @pytest.fixture
    async def instance_builder(
        self, fixture: Fixture, *args, **kwargs
    ) -> OAuthProviderBuilder:
        return OAuthProviderBuilder(
            client_id="sample_id_123",
            client_secret="sample_id_123",
            enabled=True,
            issuer_url="https://example.oidc.com",
            name="SampleOIDCProvider",
            redirect_uri="https://myapp.com/oauth/callback",
            scopes="openid profile email",
            token_type=AccessTokenType.JWT,
            vendor=ProviderVendorType.GENERIC,
            metadata=ProviderMetadata(
                authorization_endpoint="",
                token_endpoint="",
                jwks_uri="",
            ),
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[OAuthProviderBuilder]:
        return OAuthProviderBuilder

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> OAuthProvider:
        return await create_provider(fixture)

    async def test_delete_deletes_associated_userprofile(
        self,
        fixture: Fixture,
        created_instance: OAuthProvider,
        repository_instance: ExternalOAuthRepository,
    ) -> None:
        test_user = await create_test_user(fixture)
        test_user_profile = await create_test_user_profile(
            fixture, user_id=test_user.id, provider_id=created_instance.id
        )

        await repository_instance.delete_by_id(created_instance.id)

        user_profiles = await fixture.get(
            UserProfileTable.name,
            eq(UserProfileTable.c.id, test_user_profile.id),
        )
        assert user_profiles == []
