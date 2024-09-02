# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.spaces import SpacesRepository
from maasapiserver.v3.services.spaces import SpacesService
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.spaces import Space


@pytest.mark.asyncio
class TestSpacesService:
    async def test_list(self) -> None:
        db_connection = Mock(AsyncConnection)
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

    async def test_get_by_id(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = datetime.utcnow()
        expected_space = Space(
            id=0, name="test", description="descr", created=now, updated=now
        )
        spaces_repository_mock = Mock(SpacesRepository)
        spaces_repository_mock.find_by_id = AsyncMock(
            return_value=expected_space
        )
        spaces_service = SpacesService(
            connection=db_connection,
            spaces_repository=spaces_repository_mock,
        )
        space = await spaces_service.get_by_id(id=1)
        spaces_repository_mock.find_by_id.assert_called_once_with(id=1)
        assert expected_space == space
