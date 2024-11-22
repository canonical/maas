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
from maasservicelayer.db.repositories.subnets import (
    SubnetClauseFactory,
    SubnetResourceBuilder,
    SubnetsRepository,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.subnets import Subnet
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
        subnets_repository_mock.update_by_id.return_value = subnet

        mock_temporal = Mock(TemporalService)

        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=mock_temporal,
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

        await subnets_service.update_by_id(subnet.id, resource)

        subnets_repository_mock.update_by_id.assert_called_once_with(
            subnet.id, resource
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
        subnets_repository_mock.get_by_id.return_value = subnet

        mock_temporal = Mock(TemporalService)

        subnets_service = SubnetsService(
            context=Context(),
            temporal_service=mock_temporal,
            subnets_repository=subnets_repository_mock,
        )

        await subnets_service.delete_by_id(subnet.id)

        subnets_repository_mock.delete_by_id.assert_called_once_with(subnet.id)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(vlan_ids=[subnet.vlan_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
