# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on regiond."""

__all__ = [
    "service_monitor",
]

from maasserver.models.config import Config
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.service_monitor import (
    AlwaysOnService,
    Service,
    SERVICE_STATE,
    ServiceMonitor,
)


maaslog = get_maas_logger("service_monitor_service")


class BIND9Service(AlwaysOnService):
    """Monitored bind9 service."""

    name = "bind9"
    service_name = "bind9"
    snap_service_name = "bind9"


class NTPServiceOnRegion(AlwaysOnService):
    """Monitored NTP service on a region controller host."""

    name = "ntp_region"
    service_name = "ntp"
    snap_service_name = "ntp"


class ProxyService(Service):
    """Monitored proxy service."""

    name = "proxy"
    service_name = "maas-proxy"
    snap_service_name = "proxy"

    def getExpectedState(self):

        @transactional
        def db_getExpectedState():
            # Avoid recursive import.
            from maasserver import proxyconfig
            if (Config.objects.get_config("enable_http_proxy") and
                    Config.objects.get_config("http_proxy") and
                    not Config.objects.get_config("use_peer_proxy")):
                return (SERVICE_STATE.OFF,
                        "disabled, alternate proxy is configured in settings.")
            elif proxyconfig.is_config_present() is False:
                return (SERVICE_STATE.OFF, "no configuration file present.")
            else:
                return (SERVICE_STATE.ON, None)

        return deferToDatabase(db_getExpectedState)


# Global service monitor for regiond. NOTE that changes to this need to be
# mirrored in maasserver.model.services.
service_monitor = ServiceMonitor(
    BIND9Service(),
    NTPServiceOnRegion(),
    ProxyService(),
)
