# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
from typing import Any
from unittest.mock import Mock

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.staticroutes import (
    StaticRouteRequest,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ServiceCollectionV3, SubnetsService


class TestStaticRouteCreateRequest:
    @pytest.mark.parametrize(
        "ip, is_valid",
        [
            ("10.10.0.3", True),
            ("10.10.0.1", True),
            ("10.10.0.", False),
            ("10.10.0.", False),
            ("-1.10.0.1", False),
            ("0.0.0.0.0", False),
            ("fe80::3", True),
            ("fe80::::", False),
            ("::::", False),
            (None, False),  # is not nullable
        ],
    )
    def test_gateway_ip(self, ip: str | None, is_valid: bool) -> None:
        if is_valid:
            StaticRouteRequest(gateway_ip=ip, metric=10, destination_id=0)
        else:
            with pytest.raises(ValidationError):
                StaticRouteRequest(gateway_ip=ip, metric=10, destination_id=0)

    @pytest.mark.parametrize(
        "metric, is_valid",
        [
            (0, True),
            (1000, True),
            (1.1, False),  # Should be integer
            (-1, False),  # can't be negative
            (None, False),  # is not nullable
        ],
    )
    def test_metric(self, metric: Any, is_valid: bool) -> None:
        if is_valid:
            StaticRouteRequest(
                gateway_ip="10.0.0.1", metric=metric, destination_id=0
            )
        else:
            with pytest.raises(ValidationError):
                StaticRouteRequest(
                    gateway_ip="10.0.0.1", metric=metric, destination_id=0
                )

    def test_destination_id_is_mandatory(self) -> None:
        with pytest.raises(ValidationError):
            StaticRouteRequest(
                gateway_ip="10.0.0.1", metric=0, destination_id=None
            )


@pytest.mark.asyncio
class TestStaticRouteCreateRequestToBuild:
    async def test_no_destination_subnet(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = None
        request = StaticRouteRequest(
            gateway_ip="10.0.0.1", metric=0, destination_id=1
        )

        with pytest.raises(ValidationException) as e:
            await request.to_builder(
                source_subnet=Mock(Subnet), services=services_mock
            )
        assert e.value.details[0].field == "destination_id"
        assert (
            e.value.details[0].message
            == "The destination subnet with id '1' does not exist."
        )

    async def test_ip_version_mismatch_between_source_and_destination_subnets(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        source_subnet = Subnet(
            id=0,
            cidr="10.0.0.0/24",
            rdns_mode=0,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=0,
        )
        destination_subnet = Subnet(
            id=1,
            cidr="2001:db00::0/24",
            rdns_mode=0,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = destination_subnet
        request = StaticRouteRequest(
            gateway_ip="10.0.0.1", metric=0, destination_id=1
        )

        with pytest.raises(ValidationException) as e:
            await request.to_builder(
                source_subnet=source_subnet, services=services_mock
            )
        assert e.value.details[0].field == "destination_id"
        assert (
            e.value.details[0].message
            == "source and destination subnets must have be the same IP version."
        )

    async def test_gateway_ip_not_in_subnet(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        source_subnet = Subnet(
            id=0,
            cidr="10.0.0.0/24",
            rdns_mode=0,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=0,
        )
        destination_subnet = Subnet(
            id=1,
            cidr="10.0.1.0/24",
            rdns_mode=0,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = destination_subnet
        request = StaticRouteRequest(
            gateway_ip="20.0.0.1", metric=0, destination_id=1
        )

        with pytest.raises(ValidationException) as e:
            await request.to_builder(
                source_subnet=source_subnet, services=services_mock
            )
        assert e.value.details[0].field == "gateway_ip"
        assert (
            e.value.details[0].message
            == "gateway_ip must be with in the source subnet 10.0.0.0/24."
        )

    async def test_valid_build(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        source_subnet = Subnet(
            id=0,
            cidr="10.0.0.0/24",
            rdns_mode=0,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=0,
        )
        destination_subnet = Subnet(
            id=1,
            cidr="10.0.1.0/24",
            rdns_mode=0,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = destination_subnet
        request = StaticRouteRequest(
            gateway_ip="10.0.0.1", metric=0, destination_id=1
        )

        builder = await request.to_builder(
            source_subnet=source_subnet, services=services_mock
        )
        assert builder.source_id == source_subnet.id
        assert builder.destination_id == destination_subnet.id
        assert builder.metric == 0
        assert builder.gateway_ip == IPv4Address("10.0.0.1")
