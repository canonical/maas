# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.fabrics import (
    FabricsRepository,
    FabricsResourceBuilder,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.fabrics import FabricsService
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
            fabrics_repository=Mock(FabricsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return Fabric(
            id=0, name="test", description="descr", created=now, updated=now
        )


@pytest.mark.asyncio
class TestFabricsService:
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
