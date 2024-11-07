from ipaddress import IPv4Address
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.repositories.ipranges import (
    IPRangesRepository,
    IPRangesResourceBuilder,
)
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import (
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)


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
            ipranges_repository=mock_ipranges_repository,
        )

        await ipranges_service.get_dynamic_range_for_ip(subnet, sip.ip)

        mock_ipranges_repository.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, IPv4Address("10.0.0.1")
        )

    async def test_create(self):
        iprange = IPRange(
            id=1,
            type="dynamic",
            start_ip="10.0.0.1",
            end_ip="10.0.0.20",
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_ipranges_repository = Mock(IPRangesRepository)
        mock_ipranges_repository.create.return_value = iprange

        mock_temporal = Mock(TemporalService)

        ipranges_service = IPRangesService(
            Mock(AsyncConnection),
            mock_temporal,
            ipranges_repository=mock_ipranges_repository,
        )

        resource = (
            IPRangesResourceBuilder()
            .with_type(iprange.type)
            .with_start_ip(iprange.start_ip)
            .with_end_ip(iprange.end_ip)
            .with_created(iprange.created)
            .with_updated(iprange.updated)
            .build()
        )

        await ipranges_service.create(resource)

        mock_ipranges_repository.create.assert_called_once_with(resource)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            "configure-dhcp",
            ConfigureDHCPParam(ip_range_ids=[iprange.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_update(self):
        iprange = IPRange(
            id=1,
            type="dynamic",
            start_ip="10.0.0.1",
            end_ip="10.0.0.20",
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_ipranges_repository = Mock(IPRangesRepository)
        mock_ipranges_repository.update.return_value = iprange

        mock_temporal = Mock(TemporalService)

        ipranges_service = IPRangesService(
            Mock(AsyncConnection),
            mock_temporal,
            ipranges_repository=mock_ipranges_repository,
        )

        resource = (
            IPRangesResourceBuilder()
            .with_type(iprange.type)
            .with_start_ip(iprange.start_ip)
            .with_end_ip(iprange.end_ip)
            .with_created(iprange.created)
            .with_updated(iprange.updated)
            .build()
        )

        await ipranges_service.update(iprange.id, resource)

        mock_ipranges_repository.update.assert_called_once_with(
            iprange.id, resource
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            "configure-dhcp",
            ConfigureDHCPParam(ip_range_ids=[iprange.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete(self):
        iprange = IPRange(
            id=1,
            type="dynamic",
            start_ip="10.0.0.1",
            end_ip="10.0.0.20",
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_ipranges_repository = Mock(IPRangesRepository)
        mock_ipranges_repository.find_by_id.return_value = iprange

        mock_temporal = Mock(TemporalService)

        ipranges_service = IPRangesService(
            Mock(AsyncConnection),
            mock_temporal,
            ipranges_repository=mock_ipranges_repository,
        )

        await ipranges_service.delete(iprange.id)

        mock_ipranges_repository.delete.assert_called_once_with(iprange.id)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            "configure-dhcp",
            ConfigureDHCPParam(subnet_ids=[iprange.subnet_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
