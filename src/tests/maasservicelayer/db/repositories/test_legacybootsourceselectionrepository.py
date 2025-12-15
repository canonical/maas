# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.legacybootsourceselections import (
    LegacyBootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.legacybootsourceselections import (
    LegacyBootSourceSelectionClauseFactory,
    LegacyBootSourceSelectionRepository,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)
from tests.fixtures.factories.bootsourceselections import (
    create_test_legacybootsourceselection_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestLegacyBootSourceRepository(RepositoryCommonTests):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> LegacyBootSourceSelectionRepository:
        return LegacyBootSourceSelectionRepository(
            Context(connection=db_connection)
        )

    @pytest.fixture
    async def created_instance(
        self, fixture: Fixture
    ) -> LegacyBootSourceSelection:
        return await create_test_legacybootsourceselection_entry(
            fixture, "ubuntu", "noble", ["amd64"], 1
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[LegacyBootSourceSelection]:
        return [
            await create_test_legacybootsourceselection_entry(
                fixture,
                "ubuntu",
                "noble",
                [f"arch-{i}"],
                i,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return LegacyBootSourceSelectionBuilder

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> ResourceBuilder:
        return LegacyBootSourceSelectionBuilder(
            os="ubuntu",
            release="noble",
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
            boot_source_id=1,
        )


class TestLegacyBootSourceSelectionClauseFactory:
    def test_with_ids(self) -> None:
        clause = LegacyBootSourceSelectionClauseFactory.with_ids([1, 2])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselectionlegacy.id IN (1, 2)")

    def test_with_boot_source_id(self) -> None:
        clause = LegacyBootSourceSelectionClauseFactory.with_boot_source_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselectionlegacy.boot_source_id = 1")

    def test_with_os(self) -> None:
        clause = LegacyBootSourceSelectionClauseFactory.with_os("ubuntu")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselectionlegacy.os = 'ubuntu'")

    def test_with_release(self) -> None:
        clause = LegacyBootSourceSelectionClauseFactory.with_release("noble")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselectionlegacy.release = 'noble'")
