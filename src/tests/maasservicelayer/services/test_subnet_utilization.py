# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.subnet_utilization import (
    SubnetUtilizationRepository,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.subnet_utilization import (
    V3SubnetUtilizationService,
)
from maasservicelayer.services.subnets import SubnetsService


@pytest.mark.asyncio
class TestV3SubnetUtilizationService:
    @pytest.fixture(autouse=True)
    def subnet_mock(self) -> Subnet:
        return AsyncMock(Subnet)

    @pytest.fixture(autouse=True)
    def subnets_service_mock(self, subnet_mock: Mock) -> SubnetsService:
        s = Mock(SubnetsService)
        s.get_by_id.return_value = subnet_mock
        return s

    @pytest.fixture(autouse=True)
    def subnet_utilization_repo_mock(self) -> SubnetUtilizationRepository:
        return Mock(SubnetUtilizationRepository)

    @pytest.fixture(autouse=True)
    def subnet_utilization_service(
        self,
        subnets_service_mock: SubnetsService,
        subnet_utilization_repo_mock: SubnetUtilizationRepository,
    ) -> V3SubnetUtilizationService:
        return V3SubnetUtilizationService(
            context=Context(),
            subnets_service=subnets_service_mock,
            subnet_utilization_repository=subnet_utilization_repo_mock,
        )

    async def test_get_subnet_or_raise_exception(
        self,
        subnet_mock: Mock,
        subnets_service_mock: Mock,
        subnet_utilization_service: V3SubnetUtilizationService,
    ) -> None:
        s = await subnet_utilization_service._get_subnet_or_raise_exception(
            subnet_id=1
        )
        assert s == subnet_mock
        subnets_service_mock.get_by_id.assert_called_once_with(id=1)
        subnets_service_mock.reset_mock()
        subnets_service_mock.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await subnet_utilization_service._get_subnet_or_raise_exception(
                subnet_id=100
            )
        subnets_service_mock.get_by_id.assert_called_once_with(id=100)

    async def test_get_ipranges_available_for_reserved_range(
        self,
        subnet_mock: Mock,
        subnet_utilization_repo_mock: Mock,
        subnet_utilization_service: V3SubnetUtilizationService,
    ) -> None:
        await subnet_utilization_service.get_ipranges_available_for_reserved_range(
            subnet_id=1, exclude_ip_range_id=1
        )
        subnet_utilization_repo_mock.get_ipranges_available_for_reserved_range.assert_called_once_with(
            subnet=subnet_mock, exclude_ip_range_id=1
        )

    async def test_get_ipranges_available_for_dynamic_range(
        self,
        subnet_mock: Mock,
        subnet_utilization_repo_mock: Mock,
        subnet_utilization_service: V3SubnetUtilizationService,
    ) -> None:
        await subnet_utilization_service.get_ipranges_available_for_dynamic_range(
            subnet_id=1, exclude_ip_range_id=1
        )
        subnet_utilization_repo_mock.get_ipranges_available_for_dynamic_range.assert_called_once_with(
            subnet=subnet_mock, exclude_ip_range_id=1
        )

    async def test_get_ipranges_for_ip_allocation(
        self,
        subnet_mock: Mock,
        subnet_utilization_repo_mock: Mock,
        subnet_utilization_service: V3SubnetUtilizationService,
    ) -> None:
        await subnet_utilization_service.get_ipranges_for_ip_allocation(
            subnet_id=1, exclude_addresses=None
        )
        subnet_utilization_repo_mock.get_ipranges_for_ip_allocation.assert_called_once_with(
            subnet=subnet_mock, exclude_addresses=None
        )

    async def test_get_free_ipranges(
        self,
        subnet_mock: Mock,
        subnet_utilization_repo_mock: Mock,
        subnet_utilization_service: V3SubnetUtilizationService,
    ) -> None:
        await subnet_utilization_service.get_free_ipranges(subnet_id=1)
        subnet_utilization_repo_mock.get_free_ipranges.assert_called_once_with(
            subnet=subnet_mock
        )

    async def test_get_subnet_utilization(
        self,
        subnet_mock: Mock,
        subnet_utilization_repo_mock: Mock,
        subnet_utilization_service: V3SubnetUtilizationService,
    ) -> None:
        await subnet_utilization_service.get_subnet_utilization(subnet_id=1)
        subnet_utilization_repo_mock.get_subnet_utilization.assert_called_once_with(
            subnet=subnet_mock
        )

    async def test_get_ipranges_in_use(
        self,
        subnet_mock: Mock,
        subnet_utilization_repo_mock: Mock,
        subnet_utilization_service: V3SubnetUtilizationService,
    ) -> None:
        await subnet_utilization_service.get_ipranges_in_use(subnet_id=1)
        subnet_utilization_repo_mock.get_ipranges_in_use.assert_called_once_with(
            subnet=subnet_mock
        )
