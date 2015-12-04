# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service class for the monitored dhcp services."""

__all__ = [
    "DHCPv4Service",
    "DHCPv6Service",
    ]

from abc import abstractproperty
import os

from provisioningserver.dhcp import (
    DHCPv4_CONFIG_FILE,
    DHCPv6_CONFIG_FILE,
    DISABLED_DHCP_SERVER,
)
from provisioningserver.drivers.service import (
    Service,
    SERVICE_STATE,
)
from provisioningserver.path import get_path
from provisioningserver.utils.fs import read_text_file


class DHCPService(Service):
    """Abstract monitored dhcp service."""

    config_file = abstractproperty()

    def __init__(self):
        super(DHCPService, self).__init__()
        self.expected_state = self._get_starting_expected_state()

    def get_expected_state(self):
        """Return a the expected state for the dhcp service.

        The dhcp service is determined to be on when the service starts with
        `_starting_expected_state`. As the dhcp is enabled the `expected_state`
        is adjusted.
        """
        return self.expected_state

    def is_on(self):
        """Return true if the service should be on."""
        return self.expected_state == SERVICE_STATE.ON

    def on(self):
        """Set the expected state of the service to `ON`."""
        self.expected_state = SERVICE_STATE.ON

    def off(self):
        """Set the expected state of the service to `OFF`."""
        self.expected_state = SERVICE_STATE.OFF

    def _get_starting_expected_state(self):
        """Return the starting `expected_state` for this service."""
        if not os.path.exists(self.config_file):
            return SERVICE_STATE.OFF
        else:
            config_contents = read_text_file(self.config_file)
            if config_contents == DISABLED_DHCP_SERVER:
                return SERVICE_STATE.OFF
            else:
                return SERVICE_STATE.ON


class DHCPv4Service(DHCPService):

    name = "dhcp4"
    service_name = "maas-dhcpd"
    config_file = get_path(DHCPv4_CONFIG_FILE)


class DHCPv6Service(DHCPService):

    name = "dhcp6"
    service_name = "maas-dhcpd6"
    config_file = get_path(DHCPv6_CONFIG_FILE)
