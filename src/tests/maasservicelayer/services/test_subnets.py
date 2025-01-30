# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

import pytest

from maascommon.enums.subnet import RdnsMode
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    merge_configure_dhcp_param,
)
from maasservicelayer.builders.subnets import SubnetBuilder
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
from maasservicelayer.db.repositories.subnets import SubnetsRepository
from maasservicelayer.exceptions.catalog import PreconditionFailedException
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.base import BaseService
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
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonSubnetsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return SubnetsService(
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
            subnets_repository=Mock(SubnetsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return Subnet(
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
class TestSubnetsService:
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

        builder = SubnetBuilder(
            cidr=subnet.cidr,
            rdns_mode=subnet.rdns_mode,
            allow_dns=subnet.allow_dns,
            allow_proxy=subnet.allow_proxy,
            active_discovery=subnet.active_discovery,
            managed=subnet.managed,
            disabled_boot_architectures=subnet.disabled_boot_architectures,
        )

        await subnets_service.create(builder)

        subnets_repository_mock.create.assert_called_once_with(builder=builder)
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
        subnets_repository_mock.get_one.return_value = subnet
        subnets_repository_mock.update_by_id.return_value = subnet

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

        builder = SubnetBuilder(
            cidr=subnet.cidr,
            rdns_mode=subnet.rdns_mode,
            allow_dns=subnet.allow_dns,
            allow_proxy=subnet.allow_proxy,
            active_discovery=subnet.active_discovery,
            managed=subnet.managed,
            disabled_boot_architectures=subnet.disabled_boot_architectures,
        )
        query = Mock(QuerySpec)
        await subnets_service.update_one(query, builder)

        subnets_repository_mock.update_by_id.assert_called_once_with(
            id=subnet.id, builder=builder
        )
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
        subnets_repository_mock.get_one.return_value = subnet
        subnets_repository_mock.delete_by_id.return_value = subnet

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
        await subnets_service.delete_one(query)

        subnets_repository_mock.delete_by_id.assert_called_once_with(
            id=subnet.id
        )
        staticipaddress_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_subnet_id(subnet.id)
            )
        )
        ipranges_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=IPRangeClauseFactory.with_subnet_id(subnet.id)
            )
        )
        staticroutes_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
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
        reservedips_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=ReservedIPsClauseFactory.with_subnet_id(subnet.id)
            )
        )
        dhcpsnippets_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=DhcpSnippetsClauseFactory.with_subnet_id(subnet.id)
            )
        )
        nodegrouptorackcontrollers_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
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
        subnets_repository_mock.delete_by_id.return_value = subnet

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
        await subnets_service.delete_one(query, subnet.etag())

        subnets_repository_mock.delete_by_id.assert_called_once_with(
            id=subnet.id
        )
        staticipaddress_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_subnet_id(subnet.id)
            )
        )
        ipranges_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=IPRangeClauseFactory.with_subnet_id(subnet.id)
            )
        )
        staticroutes_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
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
        reservedips_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=ReservedIPsClauseFactory.with_subnet_id(subnet.id)
            )
        )
        dhcpsnippets_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=DhcpSnippetsClauseFactory.with_subnet_id(subnet.id)
            )
        )
        nodegrouptorackcontrollers_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
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
            await subnets_service.delete_one(query, "wrong-etag")

        subnets_repository_mock.delete_one.assert_not_called()
        staticipaddress_service_mock.delete_many.assert_not_called()
        ipranges_service_mock.delete_many.assert_not_called()
        staticroutes_service_mock.delete_many.assert_not_called()
        reservedips_service_mock.delete_many.assert_not_called()
        dhcpsnippets_service_mock.delete_many.assert_not_called()
        nodegrouptorackcontrollers_service_mock.delete_many.assert_not_called()
