#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Agero General Public License version 3 (see the file LICENSE).

from enum import Enum


class ZTPDeliveryMechanism(str, Enum):
    """Enum representing DHCP option numbers for ZTP provisioning."""

    DHCP_OPTION_67 = "dhcp_option_67"
    DHCP_OPTION_239 = "dhcp_option_239"
    DHCP_OPTION_240 = "dhcp_option_240"

    def __str__(self):
        return str(self.value)
