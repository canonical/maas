# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on regiond."""


from maasserver.models.config import Config
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger
from provisioningserver.proxy import config
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
            configs = Config.objects.get_configs(
                ("enable_http_proxy", "http_proxy", "use_peer_proxy")
            )
            if not configs["enable_http_proxy"]:
                return (SERVICE_STATE.OFF, "proxy disabled.")
            if (
                configs["enable_http_proxy"]
                and configs["http_proxy"]
                and not configs["use_peer_proxy"]
            ):
                return (
                    SERVICE_STATE.OFF,
                    "disabled, alternate proxy is configured in settings.",
                )
            if not config.is_config_present():
                return (SERVICE_STATE.OFF, "no configuration file present.")

            return (SERVICE_STATE.ON, None)

        return deferToDatabase(db_getExpectedState)


class HTTPService(AlwaysOnService):
    """Monitored HTTP service."""

    name = "reverse_proxy"
    service_name = "maas-http"
    snap_service_name = "http"


class TemporalService(AlwaysOnService):
    """Monitored Temporal Server service."""

    name = "temporal"
    service_name = "maas-temporal"
    snap_service_name = "temporal"


# Global service monitor for regiond. NOTE that changes to this need to be
# mirrored in maasserver.model.services.
service_monitor = ServiceMonitor(
    BIND9Service(),
    NTPServiceOnRegion(),
    SyslogServiceOnRegion(),
    ProxyService(),
    HTTPService(),
    TemporalService(),
)
