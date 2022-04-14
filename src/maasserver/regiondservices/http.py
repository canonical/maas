# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HTTP proxy service for the region controller."""

from dataclasses import dataclass
import os
from typing import Optional

from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks

from maasserver.listener import PostgresListenerService
from maasserver.models.config import Config
from maasserver.service_monitor import service_monitor
from maasserver.utils import load_template
from maasserver.utils.threads import deferToDatabase
from provisioningserver.certificates import Certificate
from provisioningserver.logger import LegacyLogger
from provisioningserver.path import get_maas_data_path
from provisioningserver.rackdservices.http import (
    compose_http_config_path,
    get_http_config_dir,
)
from provisioningserver.utils.fs import atomic_write, get_root_path, snap

log = LegacyLogger()


class RegionHTTPService(Service):
    def __init__(self, postgresListener: PostgresListenerService = None):
        super().__init__()
        self.listener = postgresListener

    @inlineCallbacks
    def startService(self):
        config = yield deferToDatabase(self._getConfiguration)
        self._configure(config)
        self._reload_service()
        super().startService()
        if self.listener is not None:
            self.listener.register("sys_reverse_proxy", self._consume_event)

    def stopService(self):
        if self.listener is not None:
            self.listener.unregister("sys_reverse_proxy", self._consume_event)
        return super().stopService()

    def _getConfiguration(self):
        configs = Config.objects.get_configs(
            ["tls_key", "tls_cert", "tls_port"]
        )
        return _Configuration(
            configs["tls_key"], configs["tls_cert"], configs["tls_port"]
        )

    def _configure(self, configuration):
        """Update the HTTP configuration for the region proxy service."""
        template = load_template("http", "regiond.nginx.conf.template")
        socket_path = os.getenv(
            "MAAS_HTTP_SOCKET_PATH",
            get_maas_data_path("maas-regiond-webapp.sock"),
        )

        tls_enabled = all(
            (configuration.port, configuration.key, configuration.cert)
        )

        key_path, cert_path = "", ""
        if tls_enabled:
            key_path, cert_path = self._create_cert_files(configuration)

        environ = {
            "http_port": 5240,
            "tls_enabled": tls_enabled,
            "tls_port": configuration.port,
            "tls_key_path": key_path,
            "tls_cert_path": cert_path,
            "socket_path": socket_path,
            "static_dir": str(get_root_path() / "usr/share/maas"),
        }
        rendered = template.substitute(environ).encode()
        target_path = compose_http_config_path("regiond.nginx.conf")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        atomic_write(rendered, target_path, overwrite=True, mode=0o644)

    def _create_cert_files(self, configuration):
        cert = Certificate.from_pem(configuration.key, configuration.cert)

        cert_path = os.path.join(
            get_http_config_dir(), "certs", "regiond-proxy.pem"
        )
        key_path = os.path.join(
            get_http_config_dir(), "certs", "regiond-proxy-key.pem"
        )

        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        os.makedirs(os.path.dirname(key_path), exist_ok=True)

        atomic_write(
            cert.certificate_pem().encode(),
            cert_path,
            overwrite=True,
            mode=0o644,
        )
        atomic_write(
            cert.private_key_pem().encode(),
            key_path,
            overwrite=True,
            mode=0o600,
        )

        return (key_path, cert_path)

    def _reload_service(self):
        if snap.running_in_snap():
            service_monitor.restartService("reverse_proxy")
        else:
            service_monitor.reloadService("reverse_proxy")

    @inlineCallbacks
    def _consume_event(self, channel, message):
        self.stopService()
        yield self.startService()


@dataclass
class _Configuration:
    """Configuration for the region's nginx reverse proxy service."""

    key: Optional[str] = None
    cert: Optional[str] = None
    port: Optional[int] = None
