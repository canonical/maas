# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on regiond."""

__all__ = [
    "service_monitor",
]

from maasserver.enum import SERVICE_STATUS
from maasserver.models.config import Config
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.service_monitor import (
    AlwaysOnService,
    Service,
    ServiceMonitor,
)


maaslog = get_maas_logger("service_monitor_service")


class BIND9Service(AlwaysOnService):
    """Monitored bind9 service."""

    name = "bind9"
    service_name = "bind9"


class NTPService(AlwaysOnService):
    """Monitored NTP service."""

    name = "ntp"
    service_name = "ntp"


class ProxyService(Service):
    """Monitored proxy service."""

    name = "proxy"
    service_name = "maas-proxy"

    def get_expected_state(self):

        @transactional
        def db_get_expected_state():
            # Avoid recursive import.
            from maasserver import proxyconfig
            if (Config.objects.get_config("enable_http_proxy") and
                    Config.objects.get_config("http_proxy")):
                return (SERVICE_STATUS.OFF,
                        "disabled, alternate proxy is configured in settings.")
            elif proxyconfig.is_config_present() is False:
                return (SERVICE_STATUS.OFF, "No configuration file present.")
            else:
                return (SERVICE_STATUS.ON, None)

        return deferToDatabase(db_get_expected_state)


# Global service monitor for regiond. NOTE that changes to this need to be
# mirrored in maasserver.model.services.
service_monitor = ServiceMonitor(
    BIND9Service(),
    NTPService(),
    ProxyService(),
)
