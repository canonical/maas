# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.resource_pools import ResourcePoolRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.fabrics import Fabric
from maasapiserver.v3.services.fabrics import FabricsService
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestFabricsService:
    async def test_list(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        fabrics_repository_mock = Mock(ResourcePoolRepository)
        fabrics_repository_mock.list_with_token = AsyncMock(
            return_value=ListResult[Fabric](items=[], next_token=None)
        )
        fabrics_service = FabricsService(
            connection=db_connection,
            fabrics_repository=fabrics_repository_mock,
        )
        fabrics_list = await fabrics_service.list(token=None, size=1)
        fabrics_repository_mock.list_with_token.assert_called_once_with(
            token=None, size=1
        )
        assert fabrics_list.next_token is None
        assert fabrics_list.items == []
