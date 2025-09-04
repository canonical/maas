# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.bootstraptokens import BootstrapTokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensRepository,
)
from maasservicelayer.models.bootstraptokens import BootstrapToken
from tests.fixtures.factories.bootstraptokens import (
    create_test_bootstraptoken_entry,
)
from tests.fixtures.factories.racks import create_test_rack_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootstrapTokensRepository(RepositoryCommonTests[BootstrapToken]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootstrapToken]:
        racks = [
            await create_test_rack_entry(fixture, name=f"rack-{i}")
            for i in range(num_objects)
        ]

        return [
            await create_test_bootstraptoken_entry(
                fixture,
                secret=f"secret-{i}",
                rack_id=racks[i].id,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootstrapToken:
        rack = await create_test_rack_entry(fixture, name="rack")

        return await create_test_bootstraptoken_entry(
            fixture,
            secret="secret",
            rack_id=rack.id,
        )

    @pytest.fixture
    async def instance_builder(
        self, fixture: Fixture, *args, **kwargs
    ) -> BootstrapTokenBuilder:
        rack = await create_test_rack_entry(fixture, name="builder-rack")
        expires_at = (
            datetime.now(timezone.utc)
            .astimezone()
            .replace(year=datetime.now(timezone.utc).year + 1)
        )

        return BootstrapTokenBuilder(
            secret="secret",
            expires_at=expires_at,
            rack_id=rack.id,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootstrapTokenBuilder]:
        return BootstrapTokenBuilder

    @pytest.fixture
    async def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootstrapTokensRepository:
        return BootstrapTokensRepository(Context(connection=db_connection))
