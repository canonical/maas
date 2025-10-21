# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
    BootSourceSelectionsRepository,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.fixtures.factories.bootsourceselections import (
    create_test_bootsourceselection_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootSourceSelectionClauseFactory:
    def test_with_id(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.id = 1")

    def test_with_boot_source_id(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_boot_source_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.boot_source_id = 1")

    def test_with_os(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_os("ubuntu")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.os = 'ubuntu'")

    def test_with_release(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_release("noble")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.release = 'noble'")


class TestCommonBootSourceSelectionRepository(
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
                arch="amd64",
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
            arch="amd64",
        )

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os="ubuntu",
            release="jammy",
            arch="amd64",
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

    async def test_update_one(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                repository_instance, instance_builder
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_multiple_results(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                2,
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            await repository_instance.update_many(
                QuerySpec(), BootSourceSelectionBuilder()
            )

    async def test_update_by_id(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                repository_instance, instance_builder
            )


class TestBootSourceSelectionRepository:
    @pytest.fixture
    def repository(self, db_connection: AsyncConnection):
        return BootSourceSelectionsRepository(
            context=Context(connection=db_connection)
        )

    async def test_get_all_highest_priority(
        self, fixture: Fixture, repository: BootSourceSelectionsRepository
    ) -> None:
        source_1 = await create_test_bootsource_entry(
            fixture, url="http://foo.com", priority=1
        )
        source_2 = await create_test_bootsource_entry(
            fixture, url="http://bar.com", priority=2
        )
        selection_1 = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=source_1.id,
        )
        selection_2 = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=source_2.id,
        )

        selections = await repository.get_all_highest_priority()
        assert len(selections) == 1
        assert selection_1 not in selections
        assert selection_2 in selections
