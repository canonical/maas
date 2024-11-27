# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.fabrics import (
    FabricsRepository,
    FabricsResourceBuilder,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.services.fabrics import FabricsService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestFabricsService:
    async def test_list(self) -> None:
        vlans_service_mock = Mock(VlansService)
        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.list.return_value = ListResult[Fabric](
            items=[], next_token=None
        )
        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )
        fabrics_list = await fabrics_service.list(token=None, size=1)
        fabrics_repository_mock.list.assert_called_once_with(
            token=None, size=1
        )
        assert fabrics_list.next_token is None
        assert fabrics_list.items == []

    async def test_get_by_id(self) -> None:
        now = utcnow()
        expected_fabric = Fabric(
            id=0, name="test", description="descr", created=now, updated=now
        )
        vlans_service_mock = Mock(VlansService)
        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.get_by_id.return_value = expected_fabric
        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )
        fabric = await fabrics_service.get_by_id(id=1)
        fabrics_repository_mock.get_by_id.assert_called_once_with(id=1)
        assert expected_fabric == fabric

    async def test_create(self) -> None:
        now = utcnow()
        expected_fabric = Fabric(
            id=0, name="test", description="descr", created=now, updated=now
        )

        vlans_service_mock = Mock(VlansService)

        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.create.return_value = expected_fabric

        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
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

    async def test_update_by_id(self) -> None:
        now = utcnow()
        fabric = Fabric(
            id=1,
            name="fabric",
            description="description",
            class_type="class",
            created=now,
            updated=now,
        )

        vlans_service_mock = Mock(VlansService)
        fabrics_repository_mock = Mock(FabricsRepository)
        fabrics_repository_mock.update_by_id.return_value = fabric
        fabrics_service = FabricsService(
            context=Context(),
            vlans_service=vlans_service_mock,
            fabrics_repository=fabrics_repository_mock,
        )

        resource = (
            FabricsResourceBuilder()
            .with_name(fabric.name)
            .with_description(fabric.description)
            .with_class_type(fabric.class_type)
            .with_created(fabric.created)
            .with_updated(fabric.updated)
            .build()
        )

        await fabrics_service.update_by_id(id=fabric.id, resource=resource)

        fabrics_repository_mock.update_by_id.assert_called_once_with(
            id=fabric.id, resource=resource
        )
