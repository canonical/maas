# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.vlans import VlansRepository
from maasapiserver.v3.services.vlans import VlansService
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.vlans import Vlan


@pytest.mark.asyncio
class TestVlansService:
    async def test_list(self) -> None:
        db_connection = Mock(AsyncConnection)
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

    async def test_get_by_id(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = datetime.utcnow()
        expected_vlan = Vlan(
            id=0,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=True,
            fabric_id=0,
            created=now,
            updated=now,
        )
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.find_by_id = AsyncMock(
            return_value=expected_vlan
        )
        vlans_service = VlansService(
            connection=db_connection,
            vlans_repository=vlans_repository_mock,
        )
        vlan = await vlans_service.get_by_id(id=1)
        vlans_repository_mock.find_by_id.assert_called_once_with(id=1)
        assert expected_vlan == vlan
