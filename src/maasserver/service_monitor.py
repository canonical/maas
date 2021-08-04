# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on regiond."""


import os

from maasserver.models.config import Config
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger
from provisioningserver.proxy import config
from provisioningserver.service_monitor import DHCPv4Service, DHCPv6Service
from provisioningserver.utils.service_monitor import (
    AlwaysOnService,
    Service,
    SERVICE_STATE,
    ServiceMonitor,
    ToggleableService,
)

maaslog = get_maas_logger("service_monitor_service")


class BIND9Service(AlwaysOnService):
    """Monitored bind9 service."""

    name = "bind9"
    service_name = "bind9"
    snap_service_name = "bind9"

    # Pass SIGKILL directly to parent.
    kill_extra_opts = ("-s", "SIGKILL")


class NTPServiceOnRegion(AlwaysOnService):
    """Monitored NTP service on a region controller host."""

    name = "ntp_region"
    service_name = "chrony"
    snap_service_name = "ntp"


class SyslogServiceOnRegion(AlwaysOnService):
    """Monitored syslog service on a region controller host."""

    name = "syslog_region"
    service_name = "maas-syslog"
    snap_service_name = "syslog"


class ProxyService(Service):
    """Monitored proxy service."""

    name = "proxy"
    service_name = "maas-proxy"
    snap_service_name = "proxy"

    def getExpectedState(self):
        @transactional
        def db_getExpectedState():
            if (
                Config.objects.get_config("enable_http_proxy")
                and Config.objects.get_config("http_proxy")
                and not Config.objects.get_config("use_peer_proxy")
            ):
                return (
                    SERVICE_STATE.OFF,
                    "disabled, alternate proxy is configured in settings.",
                )
            elif config.is_config_present() is False:
                return (SERVICE_STATE.OFF, "no configuration file present.")
            else:
                return (SERVICE_STATE.ON, None)

        return deferToDatabase(db_getExpectedState)


class ProxiedService(ToggleableService):
    def on(self, reason=None):
        if int(os.environ.get("MAAS_PROXY_MODE", 0)) == 1:
            super(ProxiedService, self).on(reason=reason)

    def any(self, reason=None):
        if int(os.environ.get("MAAS_PROXY_MODE", 0)) == 1:
            super(ProxiedService, self).any(reason=reason)


class RegionDHCPv4Service(ProxiedService, DHCPv4Service):
    pass


class RegionDHCPv6Service(ProxiedService, DHCPv6Service):
    pass


# Global service monitor for regiond. NOTE that changes to this need to be
# mirrored in maasserver.model.services.
service_monitor = ServiceMonitor(
    BIND9Service(),
    NTPServiceOnRegion(),
    SyslogServiceOnRegion(),
    ProxyService(),
    RegionDHCPv4Service(),
    RegionDHCPv6Service(),
)
