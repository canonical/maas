# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from tests.fixtures.factories.bootsourceselections import (
    create_test_bootsourceselection_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootSourceSelectionRepository(
    RepositoryCommonTests[BootSourceSelection]
):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootSourceSelection]:
        return [
            await create_test_bootsourceselection_entry(
                fixture,
                os="ubuntu",
                release=f"noble-{i}",
                boot_source_id=1,
                arches=["amd64"],
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootSourceSelection:
        return await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            boot_source_id=1,
            arches=["amd64"],
        )

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os="ubuntu",
            release="jammy",
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
            boot_source_id=1,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootSourceSelectionBuilder]:
        return BootSourceSelectionBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootSourceSelectionsRepository:
        return BootSourceSelectionsRepository(
            Context(connection=db_connection)
        )
