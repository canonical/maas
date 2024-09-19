#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maascommon.enums.bmc import BmcType
from maascommon.enums.interface import InterfaceLinkType
from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.node import (
    NodeDeviceBus,
    NodeStatus,
    NodeTypeEnum,
    SimplifiedNodeStatusEnum,
)
from maascommon.enums.subnet import RdnsMode
from maasserver.enum import (
    BMC_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_DEVICE_BUS,
    NODE_STATUS,
    NODE_TYPE,
    RDNS_MODE,
    SIMPLIFIED_NODE_STATUS,
)
from maasservicelayer.models.interfaces import InterfaceType


class TestEnumsSync:
    @pytest.mark.parametrize(
        "legacy_class, enum_class",
        [
            # When you migrate an enum, you MUST add it here!
            (BMC_TYPE, BmcType),
            (INTERFACE_LINK_TYPE, InterfaceLinkType),
            (INTERFACE_TYPE, InterfaceType),
            (IPADDRESS_TYPE, IpAddressType),
            (NODE_DEVICE_BUS, NodeDeviceBus),
            (NODE_STATUS, NodeStatus),
            (NODE_TYPE, NodeTypeEnum),
            (RDNS_MODE, RdnsMode),
            (SIMPLIFIED_NODE_STATUS, SimplifiedNodeStatusEnum),
        ],
    )
    def test_enum_sync(self, legacy_class, enum_class):
        expected_pairs = enum_class.__members__.items()
        legacy_keys = [a for a in dir(legacy_class) if not a.startswith("_")]

        assert len(expected_pairs) == len(
            legacy_keys
        ), f"Mismatch in the number of members: {len(expected_pairs)} in enum, {len(legacy_keys)} in legacy class"

        for expected_key, expected_value in expected_pairs:
            assert hasattr(
                legacy_class, expected_key
            ), f"{expected_key} is missing in {legacy_class.__name__}"
            assert (
                getattr(legacy_class, expected_key) == expected_value.value
            ), (
                f"Mismatch for {expected_key}: expected {expected_value.value}, "
                f"got {getattr(legacy_class, expected_key)}"
            )
