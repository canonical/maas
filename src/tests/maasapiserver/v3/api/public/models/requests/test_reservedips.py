# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

import pytest

from maasapiserver.v3.api.public.models.requests.reservedips import (
    ReservedIPCreateRequest,
    ReservedIPUpdateRequest,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService


@pytest.mark.asyncio
class TestReservedIPCreateRequest:
    async def test_ip_already_in_use(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        ip = IPv4Address("10.10.0.3")
        staticipaddress_mock = Mock(StaticIPAddress)
        staticipaddress_mock.ip = ip
        staticipaddress_mock.id = 1
        services_mock.staticipaddress = Mock(StaticIPAddressService)
        services_mock.staticipaddress.get_one.return_value = (
            staticipaddress_mock
        )
        services_mock.staticipaddress.get_mac_addresses.return_value = []
        with pytest.raises(ValidationException) as e:
            await ReservedIPCreateRequest(
                ip=ip, mac_address=MacAddress("00:00:00:00:00:00")
            ).to_builder(Mock(Subnet), services_mock)

        assert len(e.value.details) == 1
        assert e.value.details[0].field == "ip"
        assert (
            e.value.details[0].message
            == f"The ip {ip} is already in use by another machine."
        )
        services_mock.staticipaddress.get_one.assert_called_once_with(
            QuerySpec(where=StaticIPAddressClauseFactory.with_ip(ip))
        )
        services_mock.staticipaddress.get_mac_addresses.assert_called_once_with(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_id(
                    staticipaddress_mock.id
                )
            )
        )

    async def test_ip_inside_dynamic_range(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        ip = IPv4Address("10.10.0.3")
        services_mock.staticipaddress = Mock(StaticIPAddressService)
        services_mock.staticipaddress.get_one.return_value = None
        ip_range_mock = Mock(IPRange)
        ip_range_mock.start_ip = IPv4Address("10.10.0.0")
        ip_range_mock.end_ip = IPv4Address("10.10.0.5")
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_dynamic_range_for_ip.return_value = (
            ip_range_mock
        )
        subnet_mock = Mock(Subnet)
        subnet_mock.id = 1
        with pytest.raises(ValidationException) as e:
            await ReservedIPCreateRequest(
                ip=ip, mac_address=MacAddress("00:00:00:00:00:00")
            ).to_builder(subnet_mock, services_mock)

        assert len(e.value.details) == 1
        assert e.value.details[0].field == "ip"
        assert (
            e.value.details[0].message
            == f"The ip {ip} must be outside the dynamic range {ip_range_mock.start_ip} - {ip_range_mock.end_ip}."
        )

        services_mock.staticipaddress.get_one.assert_called_once_with(
            QuerySpec(where=StaticIPAddressClauseFactory.with_ip(ip))
        )
        services_mock.ipranges.get_dynamic_range_for_ip.assert_called_once_with(
            1, ip
        )

    async def test_ip_not_in_subnet(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        ip = IPv4Address("10.10.0.3")
        services_mock.staticipaddress = Mock(StaticIPAddressService)
        services_mock.staticipaddress.get_one.return_value = None
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_dynamic_range_for_ip.return_value = None
        subnet_mock = Mock(Subnet)
        subnet_mock.id = 1
        subnet_mock.cidr = IPv4Network("10.10.10.0/24")
        with pytest.raises(ValidationException) as e:
            await ReservedIPCreateRequest(
                ip=ip, mac_address=MacAddress("00:00:00:00:00:00")
            ).to_builder(subnet_mock, services_mock)

        assert len(e.value.details) == 1
        assert e.value.details[0].field == "ip"
        assert (
            e.value.details[0].message
            == "The provided ip is not part of the subnet."
        )
        services_mock.staticipaddress.get_one.assert_called_once_with(
            QuerySpec(where=StaticIPAddressClauseFactory.with_ip(ip))
        )

    async def test_ip_is_network_address(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        ip = IPv4Address("10.10.0.0")
        services_mock.staticipaddress = Mock(StaticIPAddressService)
        services_mock.staticipaddress.get_one.return_value = None
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_dynamic_range_for_ip.return_value = None
        subnet_mock = Mock(Subnet)
        subnet_mock.id = 1
        subnet_mock.cidr = IPv4Network("10.10.0.0/24")
        with pytest.raises(ValidationException) as e:
            await ReservedIPCreateRequest(
                ip=ip, mac_address=MacAddress("00:00:00:00:00:00")
            ).to_builder(subnet_mock, services_mock)

        assert len(e.value.details) == 1
        assert e.value.details[0].field == "ip"
        assert (
            e.value.details[0].message
            == "The network address cannot be a reserved IP."
        )
        services_mock.staticipaddress.get_one.assert_called_once_with(
            QuerySpec(where=StaticIPAddressClauseFactory.with_ip(ip))
        )

    async def test_ip_is_broadcast_address(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        ip = IPv4Address("10.10.0.255")
        services_mock.staticipaddress = Mock(StaticIPAddressService)
        services_mock.staticipaddress.get_one.return_value = None
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_dynamic_range_for_ip.return_value = None
        subnet_mock = Mock(Subnet)
        subnet_mock.id = 1
        subnet_mock.cidr = IPv4Network("10.10.0.0/24")
        with pytest.raises(ValidationException) as e:
            await ReservedIPCreateRequest(
                ip=ip, mac_address=MacAddress("00:00:00:00:00:00")
            ).to_builder(subnet_mock, services_mock)

        assert len(e.value.details) == 1
        assert e.value.details[0].field == "ip"
        assert (
            e.value.details[0].message
            == "The broadcast address cannot be a reserved IP."
        )
        services_mock.staticipaddress.get_one.assert_called_once_with(
            QuerySpec(where=StaticIPAddressClauseFactory.with_ip(ip))
        )


class TestReservedIPUpdateRequest:
    def test_to_builder_reserved_ip_wrong_ip(self):
        ip = IPv4Address("10.10.0.3")
        wrong_ip = IPv4Address("10.10.0.4")
        mac_address = MacAddress("00:00:00:00:00:00")
        request = ReservedIPUpdateRequest(
            ip=wrong_ip, mac_address=mac_address, comment="comment"
        )
        mock_reservedip = Mock(ReservedIP)
        mock_reservedip.ip = ip
        mock_reservedip.mac_address = mac_address
        with pytest.raises(ValidationException) as e:
            request.to_builder(mock_reservedip).build()

        assert len(e.value.details) == 1
        assert e.value.details[0] == BaseExceptionDetail(
            type=INVALID_ARGUMENT_VIOLATION_TYPE,
            message="The ip and mac_address of a reserved IP are immutable. Delete the entry and recreate it.",
        )

    def test_to_builder_reserved_ip_wrong_mac_address(self):
        ip = IPv4Address("10.10.0.3")
        mac_address = MacAddress("00:00:00:00:00:00")
        wrong_mac_address = MacAddress("00:00:00:00:00:01")
        request = ReservedIPUpdateRequest(
            ip=ip, mac_address=wrong_mac_address, comment="comment"
        )
        mock_reservedip = Mock(ReservedIP)
        mock_reservedip.ip = ip
        mock_reservedip.mac_address = mac_address
        with pytest.raises(ValidationException) as e:
            request.to_builder(mock_reservedip).build()

        assert len(e.value.details) == 1
        assert e.value.details[0] == BaseExceptionDetail(
            type=INVALID_ARGUMENT_VIOLATION_TYPE,
            message="The ip and mac_address of a reserved IP are immutable. Delete the entry and recreate it.",
        )

    def test_to_builder(self):
        ip = IPv4Address("10.10.0.3")
        mac_address = MacAddress("00:00:00:00:00:00")
        request = ReservedIPUpdateRequest(
            ip=ip, mac_address=mac_address, comment="comment"
        )
        mock_reservedip = Mock(ReservedIP)
        mock_reservedip.ip = ip
        mock_reservedip.mac_address = mac_address
        resource = request.to_builder(mock_reservedip).build()
        assert resource.get_values()["comment"] == "comment"
        assert resource.get_values()["updated"] is not None
