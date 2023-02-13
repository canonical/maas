# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on rackd."""


from provisioningserver.utils.service_monitor import (
    AlwaysOnService,
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


class NTPServiceOnRack(ToggleableService):
    """Monitored NTP service on a rack controller host."""

    name = "ntp_rack"
    service_name = "chrony"
    snap_service_name = "ntp"


class DNSServiceOnRack(ToggleableService):
    """Monitored DNS service on a rack controller host."""

    name = "dns_rack"
    service_name = "bind9"
    snap_service_name = "bind9"

    # Pass SIGKILL directly to parent.
    kill_extra_opts = ("-s", "SIGKILL")


class ProxyServiceOnRack(ToggleableService):
    """Monitored proxy service on a rack controller host."""

    name = "proxy_rack"
    service_name = "maas-proxy"
    snap_service_name = "proxy"


class SyslogServiceOnRack(ToggleableService):
    """Monitored syslog service on a rack controller host."""

    name = "syslog_rack"
    service_name = "maas-syslog"
    snap_service_name = "syslog"


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
)
