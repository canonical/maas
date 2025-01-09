#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from unittest.mock import Mock

from pydantic import IPvAnyAddress, ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.ipranges import (
    IPRangeCreateRequest,
    IPRangeUpdateRequest,
)
from maascommon.enums.ipranges import IPRangeType
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.exceptions.catalog import (
    ForbiddenException,
    ValidationException,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ReservedIPsService, ServiceCollectionV3

# TODO: Add tests for overlapping ranges when the check will be implemented


@pytest.mark.asyncio
class TestIPRangeCreateRequest:

    TEST_IPV4_SUBNET = Subnet(
        id=0,
        cidr=IPv4Network("10.0.0.0/24"),
        rdns_mode=RdnsMode.DEFAULT,
        allow_dns=False,
        allow_proxy=False,
        active_discovery=False,
        managed=True,
        disabled_boot_architectures=[],
        vlan_id=0,
    )

    TEST_IPV6_SUBNET = Subnet(
        id=0,
        cidr=IPv6Network("::/64"),
        rdns_mode=RdnsMode.DEFAULT,
        allow_dns=False,
        allow_proxy=False,
        active_discovery=False,
        managed=True,
        disabled_boot_architectures=[],
        vlan_id=0,
    )

    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            IPRangeCreateRequest()

        assert len(e.value.errors()) == 3
        assert {"type", "start_ip", "end_ip"} == set(
            [f["loc"][0] for f in e.value.errors()]
        )

    @pytest.mark.parametrize(
        "subnet, start_ip, end_ip, should_raise, message",
        [
            (
                TEST_IPV4_SUBNET,
                IPv4Address("10.0.0.100"),
                IPv4Address("10.0.0.120"),
                False,
                None,
            ),
            (
                TEST_IPV6_SUBNET,
                IPv6Address("::ffff:a00:62"),
                IPv6Address("::ffff:a01:00"),
                False,
                None,
            ),
            (
                TEST_IPV4_SUBNET,
                IPv4Address("10.0.0.100"),
                IPv4Address("10.0.0.99"),
                True,
                "End IP address must not be less than Start IP address.",
            ),  # wrong order
            (
                TEST_IPV6_SUBNET,
                IPv6Address("::ffff:a00:65"),
                IPv6Address("::ffff:a00:64"),
                True,
                "End IP address must not be less than Start IP address.",
            ),  # wrong order
            (
                TEST_IPV4_SUBNET,
                IPv4Address("10.0.0.0"),
                IPv4Address("10.0.0.120"),
                True,
                "Reserved network address cannot be included in IP range.",
            ),  # network address
            (
                TEST_IPV6_SUBNET,
                IPv6Address("::"),
                IPv6Address("::ffff:a00:64"),
                True,
                "Reserved network address cannot be included in IP range.",
            ),  # wrong order
            (
                TEST_IPV4_SUBNET,
                IPv4Address("10.0.0.100"),
                IPv4Address("10.0.0.255"),
                True,
                "Broadcast address cannot be included in IP range.",
            ),  # broadcast address
            (
                TEST_IPV4_SUBNET,
                IPv4Address("9.0.0.100"),
                IPv4Address("10.0.0.120"),
                True,
                "Start IP address must be within subnet: 10.0.0.0/24.",
            ),  # outside subnet
            (
                TEST_IPV4_SUBNET,
                IPv4Address("10.0.0.100"),
                IPv4Address("20.0.0.120"),
                True,
                "End IP address must be within subnet: 10.0.0.0/24.",
            ),  # outside subnet
            (
                TEST_IPV6_SUBNET,
                IPv6Address("::ffff:a00:64"),
                IPv6Address("2001:db8:3333:4444:5555:6666:7777:8888"),
                True,
                "End IP address must be within subnet: ::/64.",
            ),  # outside subnet
            (
                TEST_IPV4_SUBNET,
                IPv4Address("10.0.0.100"),
                IPv6Address("::ffff:a00:64"),
                True,
                "Start IP address and end IP address must be in the same address family.",
            ),  # different family
        ],
    )
    async def test_start_end_ips(
        self,
        subnet: Subnet,
        start_ip: IPvAnyAddress,
        end_ip: IPvAnyAddress,
        should_raise: bool,
        message: str | None,
    ):
        user = AuthenticatedUser(
            id=0, username="test", roles={UserRole.USER, UserRole.ADMIN}
        )
        if should_raise:
            with pytest.raises(ValidationException) as e:
                iprange = IPRangeCreateRequest(
                    type=IPRangeType.RESERVED, start_ip=start_ip, end_ip=end_ip
                )
                await iprange.to_builder(
                    subnet, user, Mock(ServiceCollectionV3)
                )
            assert e.value.details[0].message == message
        else:
            await IPRangeCreateRequest(
                type=IPRangeType.RESERVED, start_ip=start_ip, end_ip=end_ip
            ).to_builder(subnet, user, Mock(ServiceCollectionV3))

    async def test_reserved_range_user_with_owner(self):
        user = AuthenticatedUser(id=0, username="test", roles={UserRole.USER})
        iprange = IPRangeCreateRequest(
            type=IPRangeType.RESERVED,
            start_ip=IPv4Address("10.0.0.1"),
            end_ip=IPv4Address("10.0.0.2"),
            owner_id=0,
        )
        builder = await iprange.to_builder(
            self.TEST_IPV4_SUBNET, user, Mock(ServiceCollectionV3)
        )
        assert builder is not None

    async def test_dynamic_range_user_forbidden(self):
        user = AuthenticatedUser(id=0, username="test", roles={UserRole.USER})
        with pytest.raises(ForbiddenException):
            iprange = IPRangeCreateRequest(
                type=IPRangeType.DYNAMIC,
                start_ip=IPv4Address("10.0.0.1"),
                end_ip=IPv4Address("10.0.0.2"),
            )
            await iprange.to_builder(
                self.TEST_IPV4_SUBNET, user, Mock(ServiceCollectionV3)
            )

    async def test_dynamic_range_overlapping_reserved_ips(self):
        services_mock = Mock(ServiceCollectionV3)
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.exists_within_subnet_iprange.return_value = (
            True
        )
        user = AuthenticatedUser(
            id=0, username="test", roles={UserRole.USER, UserRole.ADMIN}
        )
        with pytest.raises(ValidationException):
            iprange = IPRangeCreateRequest(
                type=IPRangeType.DYNAMIC,
                start_ip=IPv4Address("10.0.0.1"),
                end_ip=IPv4Address("10.0.0.2"),
            )
            await iprange.to_builder(
                self.TEST_IPV4_SUBNET, user, services_mock
            )
        services_mock.reservedips.exists_within_subnet_iprange.assert_called_once_with(
            subnet_id=self.TEST_IPV4_SUBNET.id,
            start_ip=IPv4Address("10.0.0.1"),
            end_ip=IPv4Address("10.0.0.2"),
        )

    async def test_dynamic_range_ipv6_minimum_size(self):
        user = AuthenticatedUser(
            id=0, username="test", roles={UserRole.USER, UserRole.ADMIN}
        )
        with pytest.raises(ValidationException) as e:
            iprange = IPRangeCreateRequest(
                type=IPRangeType.DYNAMIC,
                start_ip=IPv6Address("0:0:0:0:0:0:0:1"),
                end_ip=IPv6Address("0:0:0:0:0:0:0:2"),
            )
            await iprange.to_builder(
                self.TEST_IPV6_SUBNET, user, Mock(ServiceCollectionV3)
            )
        assert (
            e.value.details[0].message
            == "IPv6 dynamic range must be at least 256 addresses in size."
        )


class TestIPRangeUpdateRequest:
    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            IPRangeUpdateRequest()

        assert len(e.value.errors()) == 4
        assert {"type", "start_ip", "end_ip", "owner_id"} == set(
            [f["loc"][0] for f in e.value.errors()]
        )
