# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.fabrics import FabricsRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.services.fabrics import FabricsService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestFabricsService:
    async def test_list(self) -> None:
        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.list.return_value = ListResult[Fabric](
            items=[], next_token=None
        )
        fabrics_service = FabricsService(
            context=Context(),
            fabrics_repository=fabrics_repository_mock,
        )
        fabrics_list = await fabrics_service.list(token=None, size=1)
        fabrics_repository_mock.list.assert_called_once_with(
            token=None, size=1
        )
        assert fabrics_list.next_token is None
        assert fabrics_list.items == []

    async def test_get_by_id(self) -> None:
        now = utcnow()
        expected_fabric = Fabric(
            id=0, name="test", description="descr", created=now, updated=now
        )
        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.find_by_id.return_value = expected_fabric
        fabrics_service = FabricsService(
            context=Context(),
            fabrics_repository=fabrics_repository_mock,
        )
        fabric = await fabrics_service.get_by_id(id=1)
        fabrics_repository_mock.find_by_id.assert_called_once_with(id=1)
        assert expected_fabric == fabric
