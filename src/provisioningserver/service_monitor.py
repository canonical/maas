# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on rackd."""

from abc import ABC

from provisioningserver.utils.service_monitor import (
    AlwaysOnService,
    ObserveOnlyService,
    SERVICE_STATE,
    ServiceMonitor,
    ToggleableService,
)


class HTTPService(AlwaysOnService):
    """Monitored HTTP service."""

    name = "http"
    service_name = "maas-http"
    snap_service_name = "http"


class DHCPv4Service(ObserveOnlyService):
    name = "dhcpd"
    service_name = "maas-dhcpd"
    snap_service_name = "dhcpd"


class DHCPv6Service(ObserveOnlyService):
    name = "dhcpd6"
    service_name = "maas-dhcpd6"
    snap_service_name = "dhcpd6"


class RackToggleableService(ToggleableService, ABC):
    """A helper class to prevent races between region and rack
    in region+rack deployments."""

    def __init__(self):
        # To prevent races between region and rack, accept any state
        # by default (the desired service state then will be updated
        # via RackOnlyExternalService logic)
        super().__init__(expected_state=SERVICE_STATE.ANY)


class NTPServiceOnRack(RackToggleableService):
    """Monitored NTP service on a rack controller host."""

    name = "ntp_rack"
    service_name = "chrony"
    snap_service_name = "ntp"


class DNSServiceOnRack(RackToggleableService):
    """Monitored DNS service on a rack controller host."""

    name = "dns_rack"
    service_name = "bind9"
    snap_service_name = "bind9"

    # Pass SIGKILL directly to parent.
    kill_extra_opts = ("-s", "SIGKILL")


class ProxyServiceOnRack(RackToggleableService):
    """Monitored proxy service on a rack controller host."""

    name = "proxy_rack"
    service_name = "maas-proxy"
    snap_service_name = "proxy"


class SyslogServiceOnRack(RackToggleableService):
    """Monitored syslog service on a rack controller host."""

    name = "syslog_rack"
    service_name = "maas-syslog"
    snap_service_name = "syslog"


class AgentServiceOnRack(AlwaysOnService):
    """Monitored MAAS Agent service on a rack controller host."""

    name = "agent"
    service_name = "maas-agent"
    snap_service_name = "agent"


# Global service monitor for rackd. NOTE that changes to this need to be
# mirrored in maasserver.model.services.
service_monitor = ServiceMonitor(
    HTTPService(),
    DHCPv4Service(),
    DHCPv6Service(),
    NTPServiceOnRack(),
    DNSServiceOnRack(),
    ProxyServiceOnRack(),
    SyslogServiceOnRack(),
    AgentServiceOnRack(),
)
