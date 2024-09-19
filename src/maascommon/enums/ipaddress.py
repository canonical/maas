#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class IpAddressType(IntEnum):
    """The vocabulary of possible types of `StaticIPAddress`."""

    # Note: when this enum is changed, the custom SQL query
    # in StaticIPAddressManager.get_hostname_ip_mapping() must also
    # be changed.

    # Automatically assigned IP address for a node or device out of the
    # connected clusters managed range. MUST NOT be assigned to a Interface
    # with a STICKY address of the same address family.
    AUTO = 0

    # User-specified static IP address for a node or device.
    # Permanent until removed by the user, or the node or device is deleted.
    STICKY = 1

    # User-specified static IP address.
    # Specifying a MAC address is optional. If the MAC address is not present,
    # it is created in the database (thus creating a MAC address not linked
    # to a node or a device).
    # USER_RESERVED IP addresses that correspond to a MAC address,
    # and reside within a cluster interface range, will be added to the DHCP
    # leases file.
    USER_RESERVED = 4

    # Assigned to tell the interface that it should DHCP from a managed
    # clusters dynamic range or from an external DHCP server.
    DHCP = 5

    # IP address was discovered on the interface during commissioning and/or
    # lease parsing. Only commissioning or lease parsing creates these IP
    # addresses.
    DISCOVERED = 6
