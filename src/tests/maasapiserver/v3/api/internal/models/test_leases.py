#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
import time

import pytest

from maasapiserver.v3.api.internal.models.requests.leases import (
    LeaseInfoRequest,
)
from maascommon.enums.ipaddress import LeaseAction


class TestNamedBaseModel:
    @pytest.mark.parametrize(
        "raw_mac, normalized_mac",
        [
            ("00-1B-44-11-3A-B7", "00:1b:44:11:3a:b7"),  # MAC with hyphens
            ("00:1B:44:11:3A:B7", "00:1b:44:11:3a:b7"),  # MAC with colons
            ("001B.4411.3AB7", "00:1b:44:11:3a:b7"),  # MAC with dots
            ("001B44113AB7", "00:1b:44:11:3a:b7"),  # MAC with no separators
        ],
    )
    def test_mac_address_normalized(self, raw_mac: str, normalized_mac: str):
        assert (
            LeaseInfoRequest(
                action=LeaseAction.EXPIRY,
                ip_family="ipv4",
                hostname="hostname",
                mac=raw_mac,
                ip=IPv4Address("10.0.0.1"),
                timestamp=int(time.time()),
                lease_time=30,
            ).mac
            == normalized_mac
        )

    @pytest.mark.parametrize(
        "raw_mac",
        [
            "00-1G-44-11-3A-B7",  # Invalid characters in MAC
            "00-1B-44-11-3A-BZ",  # Invalid characters in MAC
            "001B44113A",  # Too short
            "001B44113AB71234",  # Too long
        ],
    )
    def test_mac_address_normalized_invalid(self, raw_mac: str):
        with pytest.raises(ValueError):
            assert LeaseInfoRequest(
                action=LeaseAction.EXPIRY,
                ip_family="ipv4",
                hostname="hostname",
                mac=raw_mac,
                ip=IPv4Address("10.0.0.1"),
                timestamp=int(time.time()),
                lease_time=30,
            )
