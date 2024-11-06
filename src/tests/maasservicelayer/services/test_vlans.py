# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import NodeStatus
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.vlans import (
    VlansRepository,
    VlansResourceBuilder,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import (
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)


@pytest.mark.asyncio
class TestVlansService:
    async def test_list(self) -> None:
        db_connection = Mock(AsyncConnection)
        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.list = AsyncMock(
            return_value=ListResult[Vlan](items=[], next_token=None)
        )
        vlans_service = VlansService(
            connection=db_connection,
            temporal_service=Mock(TemporalService),
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )
        vlans_list = await vlans_service.list(token=None, size=1)
        vlans_repository_mock.list.assert_called_once_with(token=None, size=1)
        assert vlans_list.next_token is None
        assert vlans_list.items == []

    async def test_get_by_id(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = utcnow()
        expected_vlan = Vlan(
            id=0,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=True,
            fabric_id=0,
            created=now,
            updated=now,
        )
        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.find_by_id = AsyncMock(
            return_value=expected_vlan
        )
        vlans_service = VlansService(
            connection=db_connection,
            temporal_service=Mock(TemporalService),
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )
        vlan = await vlans_service.get_by_id(id=1)
        vlans_repository_mock.find_by_id.assert_called_once_with(id=1)
        assert expected_vlan == vlan

    async def test_get_node_vlans(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = utcnow()
        expected_vlan = Vlan(
            id=0,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=True,
            fabric_id=0,
            created=now,
            updated=now,
        )
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_node_vlans = AsyncMock(
            return_value=expected_vlan
        )
        vlans_service = VlansService(
            connection=db_connection,
            vlans_repository=vlans_repository_mock,
            temporal_service=Mock(TemporalService),
            nodes_service=Mock(NodesService),
        )
        query = QuerySpec()
        vlan = await vlans_service.get_node_vlans(query=query)
        vlans_repository_mock.get_node_vlans.assert_called_once_with(
            query=query
        )
        assert expected_vlan == vlan

    async def test_create(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=True,
            fabric_id=1,
            created=now,
            updated=now,
        )

        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.create.return_value = vlan

        mock_temporal = Mock(TemporalService)

        vlans_service = VlansService(
            connection=Mock(AsyncConnection),
            temporal_service=mock_temporal,
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )

        resource = (
            VlansResourceBuilder()
            .with_vid(vlan.vid)
            .with_name(vlan.name)
            .with_description(vlan.description)
            .with_mtu(vlan.mtu)
            .with_dhcp_on(vlan.dhcp_on)
            .with_fabric_id(vlan.fabric_id)
            .with_created(vlan.created)
            .with_updated(vlan.updated)
        )

        await vlans_service.create(resource)

        vlans_repository_mock.create.assert_called_once_with(resource)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            "configure-dhcp",
            ConfigureDHCPParam(vlan_ids=[vlan.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_update(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=True,
            fabric_id=1,
            created=now,
            updated=now,
        )

        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.update.return_value = vlan

        mock_temporal = Mock(TemporalService)

        vlans_service = VlansService(
            connection=Mock(AsyncConnection),
            temporal_service=mock_temporal,
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )

        resource = (
            VlansResourceBuilder()
            .with_vid(vlan.vid)
            .with_name(vlan.name)
            .with_description(vlan.description)
            .with_mtu(vlan.mtu)
            .with_dhcp_on(vlan.dhcp_on)
            .with_fabric_id(vlan.fabric_id)
            .with_created(vlan.created)
            .with_updated(vlan.updated)
        )

        await vlans_service.update(vlan.id, resource)

        vlans_repository_mock.update.assert_called_once_with(vlan.id, resource)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            "configure-dhcp",
            ConfigureDHCPParam(vlan_ids=[vlan.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=True,
            primary_rack_id=2,
            fabric_id=1,
            created=now,
            updated=now,
        )
        primary_rack = Node(
            id=2,
            system_id="abc",
            status=NodeStatus.DEPLOYED,
            created=now,
            updated=now,
        )

        nodes_service_mock = Mock(NodesService)
        nodes_service_mock.get_by_id.return_value = primary_rack

        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.find_by_id.return_value = vlan

        mock_temporal = Mock(TemporalService)

        vlans_service = VlansService(
            connection=Mock(AsyncConnection),
            temporal_service=mock_temporal,
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )

        await vlans_service.delete(vlan.id)

        vlans_repository_mock.delete.assert_called_once_with(vlan.id)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            "configure-dhcp",
            ConfigureDHCPParam(system_ids=[primary_rack.system_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
