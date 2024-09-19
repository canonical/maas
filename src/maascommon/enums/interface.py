#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum


class InterfaceType(str, Enum):
    """The vocabulary of possible types for `Interface`."""

    # Note: when these constants are changed, the custom SQL query
    # in StaticIPAddressManager.get_hostname_ip_mapping() must also
    # be changed.
    PHYSICAL = "physical"
    BOND = "bond"
    BRIDGE = "bridge"
    VLAN = "vlan"
    ALIAS = "alias"
    # Interface that is created when it is not linked to a node.
    UNKNOWN = "unknown"


class InterfaceLinkType(str, Enum):
    """The vocabulary of possible types to link a `Subnet` to a `Interface`."""

    AUTO = "auto"
    DHCP = "dhcp"
    STATIC = "static"
    LINK_UP = "link_up"
