# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HTTP proxy service for the region controller."""

import os

from twisted.application.service import Service

from maasserver.service_monitor import service_monitor
from maasserver.utils import load_template
from provisioningserver.logger import LegacyLogger
from provisioningserver.path import get_maas_data_path
from provisioningserver.rackdservices.http import compose_http_config_path
from provisioningserver.utils.fs import atomic_write, snap

log = LegacyLogger()


class RegionHTTPService(Service):
    def startService(self):
        self._configure()
        self._reload_service()
        super().startService()

    def _configure(self):
        """Update the HTTP configuration for the region."""
        template = load_template("http", "regiond.nginx.conf.template")
        socket_path = os.getenv(
            "MAAS_HTTP_SOCKET_PATH",
            get_maas_data_path("maas-regiond-webapp.sock"),
        )
        rendered = template.substitute({"socket_path": socket_path}).encode()

        target_path = compose_http_config_path("regiond.nginx.conf")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        atomic_write(rendered, target_path, overwrite=True, mode=0o644)

    def _reload_service(self):
        if snap.running_in_snap():
            service_monitor.restartService("reverse_proxy")
        else:
            service_monitor.reloadService("reverse_proxy")
