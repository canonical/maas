# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.node import NodeStatus
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.vlans import (
    VlanResourceBuilder,
    VlansClauseFactory,
    VlansRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    PreconditionFailedException,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam


@pytest.mark.asyncio
class TestVlansService:
    async def test_list(self) -> None:
        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.list.return_value = ListResult[Vlan](
            items=[], next_token=None
        )
        vlans_service = VlansService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )
        query = QuerySpec(where=VlansClauseFactory.with_fabric_id(fabric_id=0))
        vlans_list = await vlans_service.list(token=None, size=1, query=query)
        vlans_repository_mock.list.assert_called_once_with(
            token=None,
            size=1,
            query=query,
        )
        assert vlans_list.next_token is None
        assert vlans_list.items == []

    async def test_get_by_id(self) -> None:
        now = utcnow()
        expected_vlan = Vlan(
            id=0,
            vid=0,
            name="test",
            description="descr",
            mtu=1500,
            dhcp_on=True,
            fabric_id=0,
            created=now,
            updated=now,
        )
        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_by_id.return_value = expected_vlan
        vlans_service = VlansService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )
        vlan = await vlans_service.get_by_id(fabric_id=0, vlan_id=1)
        vlans_repository_mock.get_by_id.assert_called_once_with(id=1)
        assert expected_vlan == vlan

    async def test_get_by_id_wrong_fabric(self) -> None:
        now = utcnow()
        expected_vlan = Vlan(
            id=0,
            vid=0,
            name="test",
            description="descr",
            mtu=1500,
            dhcp_on=True,
            fabric_id=0,
            created=now,
            updated=now,
        )
        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_by_id.return_value = expected_vlan
        vlans_service = VlansService(
            Context(),
            temporal_service=Mock(TemporalService),
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )
        vlan = await vlans_service.get_by_id(fabric_id=1, vlan_id=1)
        vlans_repository_mock.get_by_id.assert_called_once_with(id=1)
        assert vlan is None

    async def test_get_node_vlans(self) -> None:
        now = utcnow()
        expected_vlan = Vlan(
            id=0,
            vid=0,
            name="test",
            description="descr",
            mtu=1500,
            dhcp_on=True,
            fabric_id=0,
            created=now,
            updated=now,
        )
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_node_vlans.return_value = expected_vlan
        vlans_service = VlansService(
            context=Context(),
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
            mtu=1500,
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
            context=Context(),
            temporal_service=mock_temporal,
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )

        resource = (
            VlanResourceBuilder()
            .with_vid(vlan.vid)
            .with_name(vlan.name)
            .with_description(vlan.description)
            .with_mtu(vlan.mtu)
            .with_dhcp_on(vlan.dhcp_on)
            .with_fabric_id(vlan.fabric_id)
            .with_created(vlan.created)
            .with_updated(vlan.updated)
            .build()
        )

        await vlans_service.create(resource)

        vlans_repository_mock.create.assert_called_once_with(resource)
        mock_temporal.register_or_update_workflow_call.assert_not_called()

    async def test_update(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=1500,
            dhcp_on=True,
            fabric_id=1,
            created=now,
            updated=now,
        )

        nodes_service_mock = Mock(NodesService)
        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.update_by_id.return_value = vlan

        mock_temporal = Mock(TemporalService)

        vlans_service = VlansService(
            context=Context(),
            temporal_service=mock_temporal,
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )

        resource = (
            VlanResourceBuilder()
            .with_vid(vlan.vid)
            .with_name(vlan.name)
            .with_description(vlan.description)
            .with_mtu(vlan.mtu)
            .with_dhcp_on(vlan.dhcp_on)
            .with_fabric_id(vlan.fabric_id)
            .with_created(vlan.created)
            .with_updated(vlan.updated)
            .build()
        )

        await vlans_service.update_by_id(vlan.id, resource)

        vlans_repository_mock.update_by_id.assert_called_once_with(
            vlan.id, resource
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
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
            mtu=1500,
            dhcp_on=True,
            primary_rack_id=2,
            fabric_id=1,
            created=now,
            updated=now,
        )
        default_vlan = vlan.copy()
        default_vlan.id = 2

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
        vlans_repository_mock.get_one.return_value = vlan
        vlans_repository_mock.get_fabric_default_vlan.return_value = (
            default_vlan
        )

        mock_temporal = Mock(TemporalService)

        vlans_service = VlansService(
            context=Context(),
            temporal_service=mock_temporal,
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )

        query = QuerySpec(
            where=ClauseFactory.and_clauses(
                [
                    VlansClauseFactory.with_id(vlan.id),
                    VlansClauseFactory.with_fabric_id(vlan.fabric_id),
                ]
            )
        )
        await vlans_service.delete(query=query)

        vlans_repository_mock.delete_by_id.assert_called_once_with(vlan.id)
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(system_ids=[primary_rack.system_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete_dhcp_disabled(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=False,
            primary_rack_id=2,
            fabric_id=1,
            created=now,
            updated=now,
        )
        default_vlan = vlan.copy()
        default_vlan.id = 2

        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_by_id.return_value = vlan
        vlans_repository_mock.get_fabric_default_vlan.return_value = (
            default_vlan
        )

        mock_temporal = Mock(TemporalService)

        vlans_service = VlansService(
            context=Context(),
            temporal_service=mock_temporal,
            nodes_service=Mock(NodesService),
            vlans_repository=vlans_repository_mock,
        )

        await vlans_service.delete_by_id(vlan.id)

        vlans_repository_mock.delete_by_id.assert_called_once_with(vlan.id)
        mock_temporal.register_or_update_workflow_call.assert_not_called()

    async def test_delete_etag_not_matching(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=False,
            primary_rack_id=2,
            fabric_id=1,
            created=now,
            updated=now,
        )
        default_vlan = vlan.copy()
        default_vlan.id = 2

        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_by_id.return_value = vlan
        vlans_repository_mock.get_fabric_default_vlan.return_value = (
            default_vlan
        )

        vlans_service = VlansService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            nodes_service=Mock(NodesService),
            vlans_repository=vlans_repository_mock,
        )

        with pytest.raises(PreconditionFailedException):
            await vlans_service.delete_by_id(vlan.id, "wrong-etag")

        vlans_repository_mock.delete.assert_not_called()

    async def test_delete_etag_matching(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=False,
            primary_rack_id=2,
            fabric_id=1,
            created=now,
            updated=now,
        )
        default_vlan = vlan.copy()
        default_vlan.id = 2

        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_by_id.return_value = vlan
        vlans_repository_mock.get_fabric_default_vlan.return_value = (
            default_vlan
        )

        vlans_service = VlansService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            nodes_service=Mock(NodesService),
            vlans_repository=vlans_repository_mock,
        )

        await vlans_service.delete_by_id(vlan.id, vlan.etag())
        vlans_repository_mock.delete_by_id.assert_called_once_with(vlan.id)

    async def test_delete_default_vlan(self) -> None:
        now = utcnow()
        vlan = Vlan(
            id=1,
            vid=0,
            name="test",
            description="descr",
            mtu=0,
            dhcp_on=False,
            primary_rack_id=2,
            fabric_id=1,
            created=now,
            updated=now,
        )

        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_by_id.return_value = vlan
        vlans_repository_mock.get_fabric_default_vlan.return_value = vlan

        vlans_service = VlansService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            nodes_service=Mock(NodesService),
            vlans_repository=vlans_repository_mock,
        )

        with pytest.raises(BadRequestException):
            await vlans_service.delete_by_id(vlan.id)
