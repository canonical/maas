# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.vlans import (
    VlansClauseFactory,
    VlansRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    PreconditionFailedException,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.vlans import Vlan, VlanBuilder
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonVlansService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return VlansService(
            context=Context(),
            vlans_repository=Mock(VlansRepository),
            temporal_service=Mock(TemporalService),
            nodes_service=Mock(NodesService),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return Vlan(
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
class TestVlansService:
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

        builder = VlanBuilder(
            vid=vlan.vid,
            name=vlan.name,
            description=vlan.description,
            mtu=vlan.mtu,
            dhcp_on=vlan.dhcp_on,
            fabric_id=vlan.fabric_id,
        )

        await vlans_service.create(builder)

        vlans_repository_mock.create.assert_called_once_with(builder=builder)
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
        vlans_repository_mock.get_by_id.return_value = vlan
        vlans_repository_mock.update_by_id.return_value = vlan

        mock_temporal = Mock(TemporalService)

        vlans_service = VlansService(
            context=Context(),
            temporal_service=mock_temporal,
            nodes_service=nodes_service_mock,
            vlans_repository=vlans_repository_mock,
        )

        builder = VlanBuilder(
            vid=vlan.vid,
            name=vlan.name,
            description=vlan.description,
            mtu=vlan.mtu,
            dhcp_on=vlan.dhcp_on,
            fabric_id=vlan.fabric_id,
        )
        await vlans_service.update_by_id(vlan.id, builder)

        vlans_repository_mock.update_by_id.assert_called_once_with(
            id=vlan.id, builder=builder
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
            power_state=PowerState.ON,
            created=now,
            updated=now,
        )

        nodes_service_mock = Mock(NodesService)
        nodes_service_mock.get_by_id.return_value = primary_rack

        vlans_repository_mock = Mock(VlansRepository)
        vlans_repository_mock.get_one.return_value = vlan
        vlans_repository_mock.delete_by_id.return_value = vlan
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
        await vlans_service.delete_one(query=query)

        vlans_repository_mock.delete_by_id.assert_called_once_with(id=vlan.id)
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
        vlans_repository_mock.delete_by_id.return_value = vlan
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

        vlans_repository_mock.delete_by_id.assert_called_once_with(id=vlan.id)
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

        vlans_repository_mock.delete_by_id.assert_not_called()

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
        vlans_repository_mock.delete_by_id.assert_called_once_with(id=vlan.id)

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
