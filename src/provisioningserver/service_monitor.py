# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on rackd."""

__all__ = [
    ]

from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import GetControllerType
from provisioningserver.utils.service_monitor import (
    AlwaysOnService,
    Service,
    SERVICE_STATE,
    ServiceMonitor,
    ToggleableService,
)


class HTTPService(AlwaysOnService):
    """Monitored HTTP service."""

    name = "http"
    service_name = "maas-http"
    snap_service_name = "http"


class DHCPv4Service(ToggleableService):

    name = "dhcpd"
    service_name = "maas-dhcpd"
    snap_service_name = "dhcpd"


class DHCPv6Service(ToggleableService):

    name = "dhcpd6"
    service_name = "maas-dhcpd6"
    snap_service_name = "dhcpd6"


class RackOnlyModeService(Service):
    """Service that should only run when in rack-only mode."""

    def getExpectedState(self):
        try:
            client = getRegionClient()
        except NoConnectionsAvailable:
            return SERVICE_STATE.ANY, None
        else:
            d = client(GetControllerType, system_id=client.localIdent)
            d.addCallback(self._getExpectedStateForControllerType)
            return d

    def _getExpectedStateForControllerType(self, controller_type):
        if controller_type["is_rack"]:
            if controller_type["is_region"]:
                return SERVICE_STATE.ANY, "managed by the region."
            else:
                return SERVICE_STATE.ON, None
        else:
            return SERVICE_STATE.ANY, None


class NTPServiceOnRack(RackOnlyModeService):
    """Monitored NTP service on a rack controller host."""

    name = "ntp_rack"
    service_name = "chrony"
    snap_service_name = "ntp"


class DNSServiceOnRack(RackOnlyModeService):
    """Monitored DNS service on a rack controller host."""

    name = "dns_rack"
    service_name = "bind9"
    snap_service_name = "bind9"


class ProxyServiceOnRack(ToggleableService):
    """Monitored proxy service on a rack controller host."""

    name = "proxy_rack"
    service_name = "maas-proxy"
    snap_service_name = "proxy"


# Global service monitor for rackd. NOTE that changes to this need to be
# mirrored in maasserver.model.services.
service_monitor = ServiceMonitor(
    HTTPService(),
    DHCPv4Service(),
    DHCPv6Service(),
    NTPServiceOnRack(),
    DNSServiceOnRack(),
    ProxyServiceOnRack(),
)
