# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.filestorage import FileStorageBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.filestorage import (
    FileStorageClauseFactory,
    FileStorageRepository,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.filestorage import FileStorage
from tests.fixtures.factories.filestorage import create_test_filestorage_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestFilestorageClauseFactory:
    def test_with_owner_id(self):
        clause = FileStorageClauseFactory.with_owner_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_filestorage.owner_id = 1"
        )


class TestFilestorageRepository(RepositoryCommonTests[FileStorage]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> FileStorageRepository:
        return FileStorageRepository(context=Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[FileStorage]:
        return [
            await create_test_filestorage_entry(
                fixture, key=f"key-{i}", filename=f"filename-{i}"
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> ResourceBuilder:
        return FileStorageBuilder(
            filename="filename", content="content", key="key", owner_id=None
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return FileStorageBuilder

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> FileStorage:
        return await create_test_filestorage_entry(fixture)

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
                num_objects,
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
            return await super().test_update_many(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                num_objects,
            )

    async def test_update_by_id(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                repository_instance, instance_builder
            )
