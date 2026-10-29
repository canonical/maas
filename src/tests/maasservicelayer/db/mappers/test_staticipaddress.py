# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from types import MappingProxyType

import pytest

from maasservicelayer.db.mappers.staticipaddress import MacAddressDataMapper
from maasservicelayer.models.fields import MacAddress


@pytest.mark.parametrize(
    "stored,expected",
    [("AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"), ("", "")],
)
def test_mac_projection_normalizes_and_preserves_empty_marker(
    stored, expected
):
    row = MappingProxyType({"mac_address": stored})

    result = MacAddressDataMapper.to_domain(row)

    assert isinstance(result, MacAddress)
    assert result == expected


def test_mac_projection_rejects_invalid_addresses():
    with pytest.raises(ValueError):
        MacAddressDataMapper.to_domain({"mac_address": "not-a-mac-address"})
