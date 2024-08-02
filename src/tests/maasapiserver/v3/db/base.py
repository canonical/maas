# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import abc
from collections.abc import Sequence
import math
from typing import Generic, TypeVar

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import MaasTimestampedBaseModel
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
    async def _created_instance(self, fixture: Fixture) -> T:
        """Fixture used to setup the necessary environment for the `test_find_*` methods.

        Returns:
            T: a created object in the database ready to be retrieved.
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
        current_token = None
        for page in range(1, total_pages + 1):
            objects_results = await repository.list(
                token=current_token, size=page_size
            )

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
            current_token = objects_results.next_token

    async def test_create(self):
        pass

    async def test_create_duplicated(self):
        pass

    async def test_find_by_id_not_found(
        self, repository_instance: BaseRepository
    ):
        instance = await repository_instance.find_by_id(-1)
        assert instance is None

    async def test_find_by_id(
        self, repository_instance: BaseRepository, _created_instance: T
    ):
        instance = await repository_instance.find_by_id(_created_instance.id)
        assert instance == _created_instance

    async def test_delete(self):
        pass

    async def test_update(self):
        pass
