# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import abc
from collections.abc import Sequence
import math
from typing import Generic, TypeVar

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    MultipleResultsException,
)
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.models.base import (
    MaasTimestampedBaseModel,
    ResourceBuilder,
    Unset,
)
from tests.maasapiserver.fixtures.db import Fixture

T = TypeVar("T", bound=MaasTimestampedBaseModel)


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class RepositoryCommonTests(abc.ABC, Generic[T]):
    @pytest.fixture
    @abc.abstractmethod
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BaseRepository:
        """Fixtures for an instance of the repository under test.

        Returns:
            BaseRepository: An instance of the repository being tested.
        """

    @pytest.fixture
    @abc.abstractmethod
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[T]:
        """Fixture used to setup the necessary environment for the `test_list` method.

        Returns:
            tuple[Sequence[T], int]: A tuple containing a list of objects relative to
                the repository and the total count of these objects.
        """

    @pytest.fixture
    @abc.abstractmethod
    async def created_instance(self, fixture: Fixture) -> T:
        """Fixture used to provide an instance of the model that has been created in the db.

        Returns:
            T: a created object in the database ready to be retrieved.
        """

    @pytest.fixture
    @abc.abstractmethod
    async def instance_builder(self, *args, **kwargs) -> ResourceBuilder:
        """Fixture used to provide a builder for the model being tested.

        Returns:
            ResourceBuilder: builder to be used for create/update methods.
        """

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        """Fixture used to provide the resource builder model.

        Returns:
            ResourceBuilder: builder class to be used to instantiate builders in tests.
        """

    @pytest.mark.parametrize("num_objects", [10])
    @pytest.mark.parametrize("page_size", range(1, 12))
    async def test_list(
        self,
        page_size: int,
        repository_instance: BaseRepository,
        _setup_test_list: Sequence[T],
        num_objects: int,
    ):
        created_objects = _setup_test_list
        repository = repository_instance
        total_pages = math.ceil(num_objects / page_size)
        for page in range(1, total_pages + 1):
            objects_results = await repository.list(page=page, size=page_size)

            if page == total_pages:  # last page may have fewer elements
                elements_count = page_size - (
                    (total_pages * page_size) % num_objects
                )
                assert len(objects_results.items) == elements_count
                for _ in range(elements_count):
                    assert created_objects.pop() in objects_results.items
            else:
                assert len(objects_results.items) == page_size
                for _ in range(page_size):
                    assert created_objects.pop() in objects_results.items

    async def test_create(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        created_resource = await repository_instance.create(instance_builder)
        assert created_resource is not None
        created_resource = created_resource.dict()
        if repository_instance.has_timestamped_fields:
            # We can expect these fields to be populated
            assert created_resource["created"] is not None
            assert created_resource["updated"] is not None

        for key, value in instance_builder.dict().items():
            if not isinstance(value, Unset):
                assert created_resource[key] == value

    async def test_create_duplicated(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        await repository_instance.create(instance_builder)
        with pytest.raises(AlreadyExistsException):
            await repository_instance.create(instance_builder)

    async def test_get_by_id_not_found(
        self, repository_instance: BaseRepository
    ):
        instance = await repository_instance.get_by_id(-1)
        assert instance is None

    async def test_get_by_id(
        self, repository_instance: BaseRepository, created_instance: T
    ):
        instance = await repository_instance.get_by_id(created_instance.id)
        assert instance == created_instance

    async def test_get_one_not_found(
        self, repository_instance: BaseRepository
    ):
        instance = await repository_instance.get_one(
            QuerySpec(
                where=Clause(
                    eq(repository_instance.get_repository_table().c.id, -1)
                )
            )
        )
        assert instance is None

    async def test_get_one(
        self, repository_instance: BaseRepository, created_instance: T
    ):
        instance = await repository_instance.get_one(
            QuerySpec(
                where=Clause(
                    eq(
                        repository_instance.get_repository_table().c.id,
                        created_instance.id,
                    )
                )
            )
        )
        assert instance == created_instance

    @pytest.mark.parametrize("num_objects", [3])
    async def test_get_one_multiple_results(
        self,
        repository_instance: BaseRepository,
        _setup_test_list: Sequence[T],
        num_objects: int,
    ):
        with pytest.raises(MultipleResultsException):
            await repository_instance.get_one(QuerySpec())

    @pytest.mark.parametrize("num_objects", [3])
    async def test_get_many(
        self,
        repository_instance: BaseRepository,
        _setup_test_list: Sequence[T],
        num_objects: int,
    ):
        instances = await repository_instance.get_many(QuerySpec())
        assert len(instances) == num_objects

    async def test_delete_one(
        self, repository_instance: BaseRepository, created_instance: T
    ):
        deleted_resource = await repository_instance.delete_one(
            QuerySpec(
                where=Clause(
                    eq(
                        repository_instance.get_repository_table().c.id,
                        created_instance.id,
                    )
                )
            )
        )
        assert deleted_resource.id == created_instance.id
        deleted = await repository_instance.get_by_id(created_instance.id)
        assert deleted is None

    @pytest.mark.parametrize("num_objects", [3])
    async def test_delete_one_multiple_results(
        self,
        repository_instance: BaseRepository,
        _setup_test_list: Sequence[T],
        num_objects: int,
    ):
        with pytest.raises(MultipleResultsException):
            await repository_instance.delete_one(QuerySpec())

    async def test_delete_by_id(
        self, repository_instance: BaseRepository, created_instance: T
    ):
        await repository_instance.delete_by_id(created_instance.id)
        deleted = await repository_instance.get_by_id(created_instance.id)
        assert deleted is None

    @pytest.mark.parametrize("num_objects", [3])
    async def test_delete_many(
        self,
        repository_instance: BaseRepository,
        _setup_test_list: Sequence[T],
        num_objects: int,
    ):
        deleted_resources = await repository_instance.delete_many(
            query=QuerySpec()
        )
        assert len(deleted_resources) == num_objects
        resources = await repository_instance.get_many(query=QuerySpec())
        assert len(resources) == 0

    async def test_update_by_id(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        created_resource = await repository_instance.create(instance_builder)
        updated_resource = await repository_instance.update_by_id(
            created_resource.id, instance_builder
        )
        assert updated_resource.updated > created_resource.updated

    async def test_update_one(
        self,
        repository_instance: BaseRepository,
        instance_builder: ResourceBuilder,
    ):
        created_resource = await repository_instance.create(instance_builder)
        updated_resource = await repository_instance.update_one(
            QuerySpec(
                where=Clause(
                    eq(
                        repository_instance.get_repository_table().c.id,
                        created_resource.id,
                    )
                )
            ),
            instance_builder,
        )
        assert updated_resource.updated > created_resource.updated

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance: BaseRepository,
        instance_builder_model: type[ResourceBuilder],
        _setup_test_list: Sequence[T],
        num_objects: int,
    ):
        builder = instance_builder_model()
        with pytest.raises(MultipleResultsException):
            await repository_instance.update_one(QuerySpec(), builder)

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance: BaseRepository,
        instance_builder_model: type[ResourceBuilder],
        _setup_test_list: Sequence[T],
        num_objects: int,
    ):
        builder = instance_builder_model()
        updated_resources = await repository_instance.update_many(
            QuerySpec(), builder
        )
        assert len(updated_resources) == 2
        assert all(resource.updated for resource in updated_resources)
