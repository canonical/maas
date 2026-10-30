# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import ip_address
from types import MappingProxyType

from netaddr import IPAddress
import pytest

from maascommon.utils.network import IPRANGE_PURPOSE, MAASIPRange
from maasservicelayer.db.mappers.subnet_utilization import (
    SubnetUtilizationRangeMapper,
)


@pytest.mark.parametrize("address_type", [ip_address, IPAddress, str])
@pytest.mark.parametrize(
    "start_ip,end_ip",
    [
        ("192.0.2.1", "192.0.2.20"),
        ("2001:db8::1", "2001:db8::20"),
    ],
)
def test_to_domain_normalizes_driver_addresses_without_mutating_row(
    address_type, start_ip: str, end_ip: str
):
    purposes = [
        IPRANGE_PURPOSE.ASSIGNED_IP,
        IPRANGE_PURPOSE.NEIGHBOUR,
        IPRANGE_PURPOSE.ASSIGNED_IP,
    ]
    row = MappingProxyType(
        {
            "start_ip": address_type(start_ip),
            "end_ip": address_type(end_ip),
            "purpose": purposes,
        }
    )

    ip_range = SubnetUtilizationRangeMapper.to_domain(row)

    assert isinstance(ip_range, MAASIPRange)
    assert ip_range.first == int(IPAddress(start_ip))
    assert ip_range.last == int(IPAddress(end_ip))
    assert ip_range.purpose == {
        IPRANGE_PURPOSE.ASSIGNED_IP,
        IPRANGE_PURPOSE.NEIGHBOUR,
    }
    assert row["start_ip"] == address_type(start_ip)
    assert row["end_ip"] == address_type(end_ip)
    assert row["purpose"] == [
        IPRANGE_PURPOSE.ASSIGNED_IP,
        IPRANGE_PURPOSE.NEIGHBOUR,
        IPRANGE_PURPOSE.ASSIGNED_IP,
    ]
    ip_range.purpose.add(IPRANGE_PURPOSE.RESERVED)
    assert IPRANGE_PURPOSE.RESERVED not in purposes


def test_to_domain_preserves_empty_purposes_and_single_address_range():
    ip_range = SubnetUtilizationRangeMapper.to_domain(
        {
            "start_ip": ip_address("2001:db8::1"),
            "end_ip": ip_address("2001:db8::1"),
            "purpose": [],
        }
    )

    assert ip_range.num_addresses == 1
    assert ip_range.purpose == set()
