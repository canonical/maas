# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.spaces import SpacesRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.spaces import Space
from maasapiserver.v3.services.spaces import SpacesService


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSpacesService:
    async def test_list(self, db_connection: AsyncConnection) -> None:
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.list = AsyncMock(
            return_value=ListResult[Space](items=[], next_token=None)
        )
        spaces_service = SpacesService(
            connection=db_connection, spaces_repository=spaces_repository_mock
        )
        spaces_list = await spaces_service.list(token=None, size=1)
        spaces_repository_mock.list.assert_called_once_with(token=None, size=1)
        assert spaces_list.next_token is None
        assert spaces_list.items == []
