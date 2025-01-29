#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolRepository,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.services import ResourcePoolsService
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonResourcePoolsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return ResourcePoolsService(
            context=Context(),
            resource_pools_repository=Mock(ResourcePoolRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return ResourcePool(
            id=2,
            name="test",
            description="",
            created=utcnow(),
            updated=utcnow(),
        )


@pytest.mark.asyncio
class TestResourcePoolsService:
    async def test_list_ids(self) -> None:
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.list_ids.return_value = {1, 2, 3}
        resource_pools_service = ResourcePoolsService(
            context=Context(),
            resource_pools_repository=resource_pool_repository_mock,
        )
        ids_list = await resource_pools_service.list_ids()
        resource_pool_repository_mock.list_ids.assert_called_once()
        assert ids_list == {1, 2, 3}
