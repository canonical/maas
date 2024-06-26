# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.spaces import SpacesRepository
from maasapiserver.v3.models.spaces import Space
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestSpacesRepository(RepositoryCommonTests[Space]):
    @pytest.fixture
    def _get_repository_instance(
        self, db_connection: AsyncConnection
    ) -> SpacesRepository:
        return SpacesRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[Space], int]:
        spaces_count = 10
        created_spaces = [
            await create_test_space_entry(
                fixture, name=str(i), description=str(i)
            )
            for i in range(spaces_count)
        ][::-1]
        return created_spaces, spaces_count
