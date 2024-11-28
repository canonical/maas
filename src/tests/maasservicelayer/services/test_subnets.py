# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

import pytest

from maascommon.enums.subnet import RdnsMode
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsClauseFactory,
)
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.db.repositories.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersClauseFactory,
)
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
)
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesClauseFactory,
)
from maasservicelayer.db.repositories.subnets import (
    SubnetClauseFactory,
    SubnetResourceBuilder,
    SubnetsRepository,
)
from maasservicelayer.exceptions.catalog import PreconditionFailedException
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.dhcpsnippets import DhcpSnippetsService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersService,
)
from maasservicelayer.services.reservedips import ReservedIPsService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.staticroutes import StaticRoutesService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam


@pytest.mark.asyncio
class TestSubnetsService:
    async def test_list(self) -> None:
        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.list.return_value = ListResult[Subnet](
            items=[], next_token=None
        )
        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            staticipaddress_service=Mock(StaticIPAddressService),
            ipranges_service=Mock(IPRangesService),
            staticroutes_service=Mock(StaticRoutesService),
            reservedips_service=Mock(ReservedIPsService),
            dhcpsnippets_service=Mock(DhcpSnippetsService),
            nodegrouptorackcontrollers_service=Mock(
                NodeGroupToRackControllersService
            ),
            subnets_repository=subnets_repository_mock,
        )
        subnets_list = await subnets_service.list(
            token=None, size=1, query=None
        )
        subnets_repository_mock.list.assert_called_once_with(
            token=None, size=1, query=None
        )
        assert subnets_list.next_token is None
        assert subnets_list.items == []

    async def test_get_by_id(self) -> None:
        now = utcnow()
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
            vlan_id=0,
            created=now,
            updated=now,
        )
        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.get_one.return_value = expected_subnet
        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            staticipaddress_service=Mock(StaticIPAddressService),
            ipranges_service=Mock(IPRangesService),
            staticroutes_service=Mock(StaticRoutesService),
            reservedips_service=Mock(ReservedIPsService),
            dhcpsnippets_service=Mock(DhcpSnippetsService),
            nodegrouptorackcontrollers_service=Mock(
                NodeGroupToRackControllersService
            ),
            subnets_repository=subnets_repository_mock,
        )
        subnet = await subnets_service.get_by_id(fabric_id=0, vlan_id=0, id=1)
        query = QuerySpec(
            where=SubnetClauseFactory.and_clauses(
                [
                    SubnetClauseFactory.with_id(1),
                    SubnetClauseFactory.with_vlan_id(0),
                    SubnetClauseFactory.with_fabric_id(0),
                ]
            )
        )
        subnets_repository_mock.get_one.assert_called_once_with(query=query)
        assert expected_subnet == subnet

    async def test_create(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
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
            vlan_id=2,
            created=now,
            updated=now,
        )

        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.create.return_value = subnet

        mock_temporal = Mock(TemporalService)

        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_service=Mock(StaticIPAddressService),
            ipranges_service=Mock(IPRangesService),
            staticroutes_service=Mock(StaticRoutesService),
            reservedips_service=Mock(ReservedIPsService),
            dhcpsnippets_service=Mock(DhcpSnippetsService),
            nodegrouptorackcontrollers_service=Mock(
                NodeGroupToRackControllersService
            ),
            subnets_repository=subnets_repository_mock,
        )

        resource = (
            SubnetResourceBuilder()
            .with_cidr(subnet.cidr)
            .with_rdns_mode(subnet.rdns_mode)
            .with_allow_dns(subnet.allow_dns)
            .with_allow_proxy(subnet.allow_proxy)
            .with_active_discovery(subnet.active_discovery)
            .with_managed(subnet.managed)
            .with_disabled_boot_architectures(
                subnet.disabled_boot_architectures
            )
            .with_created(subnet.created)
            .with_updated(subnet.updated)
            .build()
        )

        await subnets_service.create(resource)

        subnets_repository_mock.create.assert_called_once_with(resource)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(subnet_ids=[subnet.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_update(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
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
            vlan_id=2,
            created=now,
            updated=now,
        )

        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.update.return_value = subnet

        mock_temporal = Mock(TemporalService)

        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_service=Mock(StaticIPAddressService),
            ipranges_service=Mock(IPRangesService),
            staticroutes_service=Mock(StaticRoutesService),
            reservedips_service=Mock(ReservedIPsService),
            dhcpsnippets_service=Mock(DhcpSnippetsService),
            nodegrouptorackcontrollers_service=Mock(
                NodeGroupToRackControllersService
            ),
            subnets_repository=subnets_repository_mock,
        )

        resource = (
            SubnetResourceBuilder()
            .with_cidr(subnet.cidr)
            .with_rdns_mode(subnet.rdns_mode)
            .with_allow_dns(subnet.allow_dns)
            .with_allow_proxy(subnet.allow_proxy)
            .with_active_discovery(subnet.active_discovery)
            .with_managed(subnet.managed)
            .with_disabled_boot_architectures(
                subnet.disabled_boot_architectures
            )
            .with_created(subnet.created)
            .with_updated(subnet.updated)
            .build()
        )
        query = Mock(QuerySpec)
        await subnets_service.update(query, resource)

        subnets_repository_mock.update.assert_called_once_with(query, resource)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(subnet_ids=[subnet.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
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
            vlan_id=2,
            created=now,
            updated=now,
        )

        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.delete.return_value = subnet

        mock_temporal = Mock(TemporalService)
        staticipaddress_service_mock = Mock(StaticIPAddressService)
        ipranges_service_mock = Mock(IPRangesService)
        staticroutes_service_mock = Mock(StaticRoutesService)
        reservedips_service_mock = Mock(ReservedIPsService)
        dhcpsnippets_service_mock = Mock(DhcpSnippetsService)
        nodegrouptorackcontrollers_service_mock = Mock(
            NodeGroupToRackControllersService
        )

        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_service=staticipaddress_service_mock,
            ipranges_service=ipranges_service_mock,
            staticroutes_service=staticroutes_service_mock,
            reservedips_service=reservedips_service_mock,
            subnets_repository=subnets_repository_mock,
            dhcpsnippets_service=dhcpsnippets_service_mock,
            nodegrouptorackcontrollers_service=nodegrouptorackcontrollers_service_mock,
        )

        query = Mock(QuerySpec)
        await subnets_service.delete(query)

        subnets_repository_mock.delete.assert_called_once_with(query)
        staticipaddress_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=StaticIPAddressClauseFactory.with_subnet_id(subnet.id)
            )
        )
        ipranges_service_mock.delete.assert_called_once_with(
            QuerySpec(where=IPRangeClauseFactory.with_subnet_id(subnet.id))
        )
        staticroutes_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=StaticRoutesClauseFactory.or_clauses(
                    [
                        StaticRoutesClauseFactory.with_source_id(subnet.id),
                        StaticRoutesClauseFactory.with_destination_id(
                            subnet.id
                        ),
                    ]
                )
            )
        )
        reservedips_service_mock.delete.assert_called_once_with(
            QuerySpec(where=ReservedIPsClauseFactory.with_subnet_id(subnet.id))
        )
        dhcpsnippets_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=DhcpSnippetsClauseFactory.with_subnet_id(subnet.id)
            )
        )
        nodegrouptorackcontrollers_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=NodeGroupToRackControllersClauseFactory.with_subnet_id(
                    subnet.id
                )
            )
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(vlan_ids=[subnet.vlan_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete_etag_matching(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
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
            vlan_id=2,
            created=now,
            updated=now,
        )

        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.get_one.return_value = subnet
        subnets_repository_mock.delete.return_value = subnet

        mock_temporal = Mock(TemporalService)
        staticipaddress_service_mock = Mock(StaticIPAddressService)
        ipranges_service_mock = Mock(IPRangesService)
        staticroutes_service_mock = Mock(StaticRoutesService)
        reservedips_service_mock = Mock(ReservedIPsService)
        dhcpsnippets_service_mock = Mock(DhcpSnippetsService)
        nodegrouptorackcontrollers_service_mock = Mock(
            NodeGroupToRackControllersService
        )

        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_service=staticipaddress_service_mock,
            ipranges_service=ipranges_service_mock,
            staticroutes_service=staticroutes_service_mock,
            reservedips_service=reservedips_service_mock,
            subnets_repository=subnets_repository_mock,
            dhcpsnippets_service=dhcpsnippets_service_mock,
            nodegrouptorackcontrollers_service=nodegrouptorackcontrollers_service_mock,
        )

        query = Mock(QuerySpec)
        await subnets_service.delete(query, subnet.etag())

        subnets_repository_mock.delete.assert_called_once_with(query)
        staticipaddress_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=StaticIPAddressClauseFactory.with_subnet_id(subnet.id)
            )
        )
        ipranges_service_mock.delete.assert_called_once_with(
            QuerySpec(where=IPRangeClauseFactory.with_subnet_id(subnet.id))
        )
        staticroutes_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=StaticRoutesClauseFactory.or_clauses(
                    [
                        StaticRoutesClauseFactory.with_source_id(subnet.id),
                        StaticRoutesClauseFactory.with_destination_id(
                            subnet.id
                        ),
                    ]
                )
            )
        )
        reservedips_service_mock.delete.assert_called_once_with(
            QuerySpec(where=ReservedIPsClauseFactory.with_subnet_id(subnet.id))
        )
        dhcpsnippets_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=DhcpSnippetsClauseFactory.with_subnet_id(subnet.id)
            )
        )
        nodegrouptorackcontrollers_service_mock.delete.assert_called_once_with(
            QuerySpec(
                where=NodeGroupToRackControllersClauseFactory.with_subnet_id(
                    subnet.id
                )
            )
        )

    async def test_delete_etag_not_matching(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
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
            vlan_id=2,
            created=now,
            updated=now,
        )

        subnets_repository_mock = Mock(SubnetsRepository)
        subnets_repository_mock.get_one.return_value = subnet

        mock_temporal = Mock(TemporalService)
        staticipaddress_service_mock = Mock(StaticIPAddressService)
        ipranges_service_mock = Mock(IPRangesService)
        staticroutes_service_mock = Mock(StaticRoutesService)
        reservedips_service_mock = Mock(ReservedIPsService)
        dhcpsnippets_service_mock = Mock(DhcpSnippetsService)
        nodegrouptorackcontrollers_service_mock = Mock(
            NodeGroupToRackControllersService
        )

        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_service=staticipaddress_service_mock,
            ipranges_service=ipranges_service_mock,
            staticroutes_service=staticroutes_service_mock,
            reservedips_service=reservedips_service_mock,
            subnets_repository=subnets_repository_mock,
            dhcpsnippets_service=dhcpsnippets_service_mock,
            nodegrouptorackcontrollers_service=nodegrouptorackcontrollers_service_mock,
        )

        query = Mock(QuerySpec)
        with pytest.raises(PreconditionFailedException):
            await subnets_service.delete(query, "wrong-etag")

        subnets_repository_mock.delete.assert_not_called()
        staticipaddress_service_mock.delete.assert_not_called()
        ipranges_service_mock.delete.assert_not_called()
        staticroutes_service_mock.delete.assert_not_called()
        reservedips_service_mock.delete.assert_not_called()
        dhcpsnippets_service_mock.delete.assert_not_called()
        nodegrouptorackcontrollers_service_mock.delete.assert_not_called()
