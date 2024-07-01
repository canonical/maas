# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.subnets import SubnetsRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.subnets import Subnet
from maasapiserver.v3.services.subnets import SubnetsService


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSubnetsService:
    async def test_list(self, db_connection: AsyncConnection) -> None:
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
