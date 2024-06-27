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
        self, fixture: Fixture
    ) -> tuple[Sequence[T], int]:
        """Fixture used to setup the necessary environment for the `test_list` method.

        Returns:
            tuple[Sequence[T], int]: A tuple containing a list of objects relative to
                the repository and the total count of these objects.
        """

    @pytest.mark.parametrize("page_size", range(1, 12))
    async def test_list(
        self,
        page_size: int,
        repository_instance: BaseRepository,
        _setup_test_list: tuple[Sequence[T], int],
    ):
        created_objects, objects_count = _setup_test_list
        repository = repository_instance
        total_pages = math.ceil(objects_count / page_size)
        current_token = None
        for page in range(1, total_pages + 1):
            objects_results = await repository.list(
                token=current_token, size=page_size
            )
            if page == total_pages:  # last page may have fewer elements
                assert len(objects_results.items) == (
                    page_size - ((total_pages * page_size) % objects_count)
                )
            else:
                assert len(objects_results.items) == page_size

            for obj in created_objects[
                ((page - 1) * page_size) : ((page * page_size))
            ]:
                assert obj in objects_results.items
            current_token = objects_results.next_token

    async def test_create(self):
        pass

    async def test_create_duplicated(self):
        pass

    async def test_find_by_id(self):
        pass

    async def test_delete(self):
        pass

    async def test_update(self):
        pass
