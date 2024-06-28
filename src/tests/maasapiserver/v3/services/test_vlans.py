# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.vlans import VlansRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.vlans import Vlan
from maasapiserver.v3.services.vlans import VlansService


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestVlansService:
    async def test_list(self, db_connection: AsyncConnection) -> None:
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.list = AsyncMock(
            return_value=ListResult[Vlan](items=[], next_token=None)
        )
        vlans_service = VlansService(
            connection=db_connection, vlans_repository=vlans_repository_mock
        )
        vlans_list = await vlans_service.list(token=None, size=1)
        vlans_repository_mock.list.assert_called_once_with(token=None, size=1)
        assert vlans_list.next_token is None
        assert vlans_list.items == []
