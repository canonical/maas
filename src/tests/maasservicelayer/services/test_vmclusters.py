#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.vmcluster import VmClustersRepository
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.vmcluster import VmCluster
from maasservicelayer.services import VmClustersService
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonVmClusterService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return VmClustersService(
            context=Context(), vmcluster_repository=Mock(VmClustersRepository)
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return VmCluster(
            id=0,
            created=now,
            updated=now,
        )


@pytest.mark.asyncio
class TestVmClusterService:
    async def test_move_to_zone(self) -> None:
        vmcluster_repository_mock = Mock(VmClustersRepository)
        vmcluster_service = VmClustersService(
            context=Context(), vmcluster_repository=vmcluster_repository_mock
        )
        await vmcluster_service.move_to_zone(0, 0)
        vmcluster_repository_mock.move_to_zone.assert_called_once_with(0, 0)
