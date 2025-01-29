#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.ipranges import IPRangeType
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsClauseFactory,
)
from maasservicelayer.db.repositories.ipranges import (
    IPRangeClauseFactory,
    IPRangesRepository,
)
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.ipranges import IPRange, IPRangeBuilder
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.dhcpsnippets import DhcpSnippetsService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonIPRangesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return IPRangesService(
            Mock(AsyncConnection),
            Mock(TemporalService),
            Mock(DhcpSnippetsService),
            ipranges_repository=Mock(IPRangesRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return IPRange(
            id=1,
            type=IPRangeType.DYNAMIC,
            start_ip=IPv4Address("10.0.0.1"),
            end_ip=IPv4Address("10.0.0.20"),
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

    async def test_create(self, service_instance, test_instance):
        # pre_create_hook tested in the next tests
        service_instance.pre_create_hook = AsyncMock()
        return await super().test_create(service_instance, test_instance)

    async def test_update_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


@pytest.mark.asyncio
class TestIPRangesService:
    async def test_get_dynamic_range_for_ip(self) -> None:
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=utcnow(),
            updated=utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            disabled_boot_architectures=[],
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.1",
            subnet_id=subnet.id,
            lease_time=600,
            created=utcnow(),
            updated=utcnow(),
            alloc_type=IpAddressType.DISCOVERED,
        )

        mock_ipranges_repository = Mock(IPRangesRepository)

        ipranges_service = IPRangesService(
            Mock(AsyncConnection),
            Mock(TemporalService),
            Mock(DhcpSnippetsService),
            ipranges_repository=mock_ipranges_repository,
        )

        await ipranges_service.get_dynamic_range_for_ip(subnet, sip.ip)

        mock_ipranges_repository.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, IPv4Address("10.0.0.1")
        )

    async def test_create(self):
        iprange = IPRange(
            id=1,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.1",
            end_ip="10.0.0.20",
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_ipranges_repository = Mock(IPRangesRepository)
        mock_ipranges_repository.create.return_value = iprange
        mock_ipranges_repository.exists.return_value = False

        mock_temporal = Mock(TemporalService)

        ipranges_service = IPRangesService(
            context=Context(),
            temporal_service=mock_temporal,
            dhcpsnippets_service=Mock(DhcpSnippetsService),
            ipranges_repository=mock_ipranges_repository,
        )

        builder = IPRangeBuilder(
            type=iprange.type,
            start_ip=iprange.start_ip,
            end_ip=iprange.end_ip,
            subnet_id=2,
        )

        await ipranges_service.create(builder)

        mock_ipranges_repository.create.assert_called_once_with(
            builder=builder
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(ip_range_ids=[iprange.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_create_already_existing(self):
        iprange = IPRange(
            id=1,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.1",
            end_ip="10.0.0.20",
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_ipranges_repository = Mock(IPRangesRepository)
        mock_ipranges_repository.create.return_value = iprange
        mock_ipranges_repository.exists.return_value = True

        mock_temporal = Mock(TemporalService)

        ipranges_service = IPRangesService(
            context=Context(),
            temporal_service=mock_temporal,
            dhcpsnippets_service=Mock(DhcpSnippetsService),
            ipranges_repository=mock_ipranges_repository,
        )
        builder = IPRangeBuilder(
            type=iprange.type,
            start_ip=iprange.start_ip,
            end_ip=iprange.end_ip,
            subnet_id=2,
        )

        with pytest.raises(AlreadyExistsException):
            await ipranges_service.create(builder)
        mock_ipranges_repository.exists.assert_called_once_with(
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_type(iprange.type),
                        IPRangeClauseFactory.with_start_ip(iprange.start_ip),
                        IPRangeClauseFactory.with_start_ip(iprange.end_ip),
                        IPRangeClauseFactory.with_subnet_id(iprange.subnet_id),
                    ]
                )
            )
        )

    async def test_update(self):
        iprange = IPRange(
            id=1,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.1",
            end_ip="10.0.0.20",
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_ipranges_repository = Mock(IPRangesRepository)
        mock_ipranges_repository.get_by_id.return_value = iprange
        mock_ipranges_repository.update_by_id.return_value = iprange

        mock_temporal = Mock(TemporalService)

        ipranges_service = IPRangesService(
            context=Context(),
            temporal_service=mock_temporal,
            dhcpsnippets_service=Mock(DhcpSnippetsService),
            ipranges_repository=mock_ipranges_repository,
        )

        builder = IPRangeBuilder(
            type=iprange.type,
            start_ip=iprange.start_ip,
            end_ip=iprange.end_ip,
            subnet_id=2,
        )

        await ipranges_service.update_by_id(iprange.id, builder)

        mock_ipranges_repository.update_by_id.assert_called_once_with(
            id=iprange.id, builder=builder
        )

        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(ip_range_ids=[iprange.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete(self):
        iprange = IPRange(
            id=1,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.1",
            end_ip="10.0.0.20",
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_ipranges_repository = Mock(IPRangesRepository)
        mock_ipranges_repository.get_by_id.return_value = iprange
        mock_ipranges_repository.delete_by_id.return_value = iprange

        mock_temporal = Mock(TemporalService)
        dhcpsnippets_service_mock = Mock(DhcpSnippetsService)

        ipranges_service = IPRangesService(
            context=Context(),
            temporal_service=mock_temporal,
            dhcpsnippets_service=dhcpsnippets_service_mock,
            ipranges_repository=mock_ipranges_repository,
        )

        await ipranges_service.delete_by_id(iprange.id)

        mock_ipranges_repository.delete_by_id.assert_called_once_with(
            id=iprange.id
        )
        dhcpsnippets_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=DhcpSnippetsClauseFactory.with_iprange_id(iprange.id)
            )
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(subnet_ids=[iprange.subnet_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
