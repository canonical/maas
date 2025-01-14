# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.interface import InterfaceType
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.fabrics import (
    FabricsRepository,
    FabricsResourceBuilder,
)
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.exceptions.catalog import BadRequestException
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.fabrics import FabricsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonFabricsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return FabricsService(
            context=Context(),
            vlans_service=Mock(VlansService),
            subnets_service=Mock(SubnetsService),
            interfaces_service=Mock(InterfacesService),
            fabrics_repository=Mock(FabricsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return Fabric(
            id=1, name="test", description="descr", created=now, updated=now
        )

    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


@pytest.mark.asyncio
class TestFabricsService:
    async def test_create(self) -> None:
        now = utcnow()
        expected_fabric = Fabric(
            id=0, name="test", description="descr", created=now, updated=now
        )

        vlans_service_mock = Mock(VlansService)

        subnets_service_mock = Mock(SubnetsService)

        interfaces_service_mock = Mock(InterfacesService)

        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.create.return_value = expected_fabric

        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            subnets_service=subnets_service_mock,
            interfaces_service=interfaces_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )

        resource = (
            FabricsResourceBuilder()
            .with_name("test")
            .with_description("descr")
            .with_created(now)
            .with_updated(now)
            .build()
        )

        actual_fabric = await fabrics_service.create(resource)
        assert expected_fabric == actual_fabric
        fabrics_repository_mock.create.assert_called_once()

        # Check Default VLAN created on Fabric creation
        vlans_service_mock.create.assert_called_once()
        create_vlan_args = vlans_service_mock.create.call_args.kwargs[
            "resource"
        ].get_values()
        assert create_vlan_args["fabric_id"] == expected_fabric.id
        assert create_vlan_args["vid"] == 0
        assert create_vlan_args["name"] == "Default VLAN"
        assert create_vlan_args["mtu"] == 1500
        assert create_vlan_args["dhcp_on"] is False

    async def test_delete_by_id(self) -> None:
        fabric_to_delete = Fabric(
            id=1,
            name="Test fabric",
        )
        vlan_1 = Vlan(
            id=0,
            vid=0,
            fabric_id=1,
            description="Test VLAN description",
            mtu=3500,
            dhcp_on=False,
        )

        vlans_service_mock = Mock(VlansService)
        vlans_service_mock.get_many.side_effect = [
            [vlan_1],
        ]

        subnets_service_mock = Mock(SubnetsService)

        interfaces_service_mock = Mock(InterfacesService)

        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.get_by_id.return_value = fabric_to_delete
        fabrics_repository_mock.delete_by_id.return_value = fabric_to_delete

        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            subnets_service=subnets_service_mock,
            interfaces_service=interfaces_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )

        await fabrics_service.delete_by_id(id=fabric_to_delete.id)

        fabrics_repository_mock.delete_by_id.assert_called_once_with(
            id=fabric_to_delete.id
        )

        subnets_service_mock.get_many.assert_called_once()
        interfaces_service_mock.get_interfaces_in_fabric.assert_called_once()

        # TODO: Replace `get_many` with `delete_many` once its implemented.
        vlans_service_mock.get_many.assert_called_once()

    async def test_delete_by_id_default_fabric(self) -> None:
        fabric_to_delete = Fabric(id=0)

        vlans_service_mock = Mock(VlansService)
        subnets_service_mock = Mock(SubnetsService)
        interfaces_service_mock = Mock(InterfacesService)

        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.get_by_id.return_value = fabric_to_delete

        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            subnets_service=subnets_service_mock,
            interfaces_service=interfaces_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )

        with pytest.raises(BadRequestException):
            await fabrics_service.delete_by_id(id=fabric_to_delete.id)

        subnets_service_mock.get_many.assert_not_called()
        interfaces_service_mock.get_interfaces_in_fabric.assert_not_called()

        # TODO: Replace `get_many` with `delete_many` once its implemented.
        vlans_service_mock.get_many.assert_not_called()

    async def test_delete_by_id_has_subnets(self) -> None:
        fabric_to_delete = Fabric(id=1)

        vlans_service_mock = Mock(VlansService)

        subnets_service_mock = Mock(SubnetsService)
        subnets_service_mock.get_many.return_value = [
            Subnet(
                id=0,
                cidr="10.0.0.1/24",
                rdns_mode=RdnsMode.DEFAULT,
                allow_dns=False,
                allow_proxy=False,
                active_discovery=False,
                managed=False,
                disabled_boot_architectures=[],
                vlan_id=0,
            )
        ]

        interfaces_service_mock = Mock(InterfacesService)

        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.get_by_id.return_value = fabric_to_delete

        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            subnets_service=subnets_service_mock,
            interfaces_service=interfaces_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )

        with pytest.raises(BadRequestException):
            await fabrics_service.delete_by_id(id=fabric_to_delete.id)

        subnets_service_mock.get_many.assert_called_once_with(
            query=QuerySpec(
                where=SubnetClauseFactory.with_fabric_id(
                    fabric_id=fabric_to_delete.id
                )
            )
        )
        interfaces_service_mock.get_interfaces_in_fabric.assert_not_called()

        # TODO: Replace `get_many` with `delete_many` once its implemented.
        vlans_service_mock.get_many.assert_not_called()

    async def test_delete_by_id_has_connected_interfaces(self) -> None:
        fabric_to_delete = Fabric(
            id=1,
        )
        interface_1 = Interface(
            id=0,
            name="Test interface",
            type=InterfaceType.PHYSICAL,
        )

        vlans_service_mock = Mock(VlansService)

        subnets_service_mock = Mock(SubnetsService)
        subnets_service_mock.get_many.return_value = []

        interfaces_service_mock = Mock(InterfacesService)
        interfaces_service_mock.get_interfaces_in_fabric.side_effect = [
            [interface_1]
        ]

        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.get_by_id.return_value = fabric_to_delete

        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            subnets_service=subnets_service_mock,
            interfaces_service=interfaces_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )

        with pytest.raises(BadRequestException):
            await fabrics_service.delete_by_id(id=fabric_to_delete.id)

        subnets_service_mock.get_many.assert_called_once_with(
            query=QuerySpec(
                where=SubnetClauseFactory.with_fabric_id(
                    fabric_id=fabric_to_delete.id
                )
            )
        )
        interfaces_service_mock.get_interfaces_in_fabric.assert_called_once_with(
            fabric_id=fabric_to_delete.id
        )

        # TODO: Replace `get_many` with `delete_many` once its implemented.
        vlans_service_mock.get_many.assert_not_called()
