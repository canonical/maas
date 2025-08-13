# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

from netaddr import IPNetwork
import pytest

from maascommon.enums.subnet import RdnsMode
from maascommon.utils.network import IPRANGE_PURPOSE, MAASIPRange, MAASIPSet
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ui_subnets import UISubnetsRepository
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.services.subnet_utilization import (
    V3SubnetUtilizationService,
)
from maasservicelayer.services.ui_subnets import UISubnetsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ReadOnlyServiceCommonTests


class TestUISubnetsService(ReadOnlyServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> UISubnetsService:
        return UISubnetsService(
            context=Context(),
            ui_subnets_repository=Mock(UISubnetsRepository),
            subnets_utilization_service=Mock(V3SubnetUtilizationService),
        )

    @pytest.fixture
    def test_instance(self) -> UISubnet:
        return UISubnet(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="10.0.0.1/24",
            cidr=IPv4Network("10.0.0.1"),
            description="",
            rdns_mode=RdnsMode.DEFAULT,
            gateway_ip=IPv4Address("10.0.0.1"),
            dns_servers=[],
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
            vlan_vid=0,
            vlan_name="Default VLAN",
            vlan_dhcp_on=False,
            vlan_external_dhcp=None,
            vlan_relay_vlan_id=None,
            fabric_id=1,
            fabric_name="fabric-1",
            space_id=1,
            space_name="space-1",
        )

    async def test_calculate_statistics_for_subnet(
        self, test_instance: UISubnet, service_instance: UISubnetsService
    ) -> None:
        service_instance.subnets_utilization_service.get_subnet_utilization.return_value = MAASIPSet(
            ranges=[
                MAASIPRange(
                    start="10.0.0.1", purpose=IPRANGE_PURPOSE.GATEWAY_IP
                ),
                MAASIPRange(
                    start="10.0.0.2",
                    end="10.0.0.254",
                    purpose=IPRANGE_PURPOSE.UNUSED,
                ),
            ],
            cidr=IPNetwork("10.0.0.1/24"),
        )
        updated_subnet = (
            await service_instance.calculate_statistics_for_subnet(
                test_instance
            )
        )

        assert updated_subnet.statistics is not None

        service_instance.subnets_utilization_service.get_subnet_utilization.assert_awaited_once_with(
            test_instance.id
        )

    async def test_calculate_statistics_for_subnets(
        self, test_instance: UISubnet, service_instance: UISubnetsService
    ) -> None:
        service_instance.subnets_utilization_service.get_subnet_utilization.return_value = MAASIPSet(
            ranges=[
                MAASIPRange(
                    start="10.0.0.1", purpose=IPRANGE_PURPOSE.GATEWAY_IP
                ),
                MAASIPRange(
                    start="10.0.0.2",
                    end="10.0.0.254",
                    purpose=IPRANGE_PURPOSE.UNUSED,
                ),
            ],
            cidr=IPNetwork("10.0.0.1/24"),
        )
        updated_subnets = (
            await service_instance.calculate_statistics_for_subnets(
                [test_instance]
            )
        )
        assert updated_subnets[0].statistics is not None

        service_instance.subnets_utilization_service.get_subnet_utilization.assert_awaited_once_with(
            test_instance.id
        )
