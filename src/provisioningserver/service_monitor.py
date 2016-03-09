# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on rackd."""

__all__ = [
    ]

from provisioningserver.utils.service_monitor import (
    Service,
    SERVICE_STATE,
    ServiceMonitor,
)


class DHCPService(Service):
    """Abstract monitored dhcp service."""

    def __init__(self):
        super(DHCPService, self).__init__()
        self.expected_state = SERVICE_STATE.OFF

    def get_expected_state(self):
        """Return a the expected state for the dhcp service.

        The dhcp service always starts as off. Once the rackd starts dhcp
        `expected_state` will be set to ON.
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


class DHCPv4Service(DHCPService):

    name = "dhcp4"
    service_name = "maas-dhcpd"


class DHCPv6Service(DHCPService):

    name = "dhcp6"
    service_name = "maas-dhcpd6"


class TGTService(Service):
    """Monitored tgt service."""

    name = "tgt"
    service_name = "tgt"

    def get_expected_state(self):
        """Return a the expected state for the tgt service.

        The tgt service should always be on. No condition exists where it
        should be off.
        """
        return SERVICE_STATE.ON


# Global service monitor for rackd.
service_monitor = ServiceMonitor(
    DHCPv4Service(),
    DHCPv6Service(),
    TGTService(),
)
