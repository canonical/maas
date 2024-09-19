# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from ipaddress import IPv4Address, IPv4Network
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.db.repositories.subnets import SubnetsRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.subnets import SubnetsService


@pytest.mark.asyncio
class TestSubnetsService:
    async def test_list(self) -> None:
        db_connection = Mock(AsyncConnection)
        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.list = AsyncMock(
            return_value=ListResult[Subnet](items=[], next_token=None)
        )
        subnets_service = SubnetsService(
            connection=db_connection,
            subnets_repository=subnets_repository_mock,
        )
        subnets_list = await subnets_service.list(token=None, size=1)
        subnets_repository_mock.list.assert_called_once_with(
            token=None, size=1
        )
        assert subnets_list.next_token is None
        assert subnets_list.items == []

    async def test_get_by_id(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = datetime.utcnow()
        expected_subnet = Subnet(
            id=0,
            name="my subnet",
            description="subnet description",
            cidr=IPv4Network("10.0.0.0/24"),
            rdns_mode=RdnsMode.DEFAULT,
            gateway_ip=IPv4Address("10.0.0.1"),
            dns_servers=[],
            allow_dns=True,
            allow_proxy=True,
            active_discovery=False,
            managed=True,
            disabled_boot_architectures=[],
            created=now,
            updated=now,
        )
        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.find_by_id = AsyncMock(
            return_value=expected_subnet
        )
        subnets_service = SubnetsService(
            connection=db_connection,
            subnets_repository=subnets_repository_mock,
        )
        subnet = await subnets_service.get_by_id(id=1)
        subnets_repository_mock.find_by_id.assert_called_once_with(id=1)
        assert expected_subnet == subnet
