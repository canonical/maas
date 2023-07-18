# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HTTP proxy service for the region controller."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks

from maasserver.listener import PostgresListenerService
from maasserver.models.config import Config
from maasserver.regiondservices import certificate_expiration_check
from maasserver.service_monitor import service_monitor
from maasserver.utils import load_template
from maasserver.utils.threads import deferToDatabase
from maasserver.workers import WorkersService
from provisioningserver.certificates import Certificate
from provisioningserver.logger import LegacyLogger
from provisioningserver.path import get_maas_data_path
from provisioningserver.rackdservices.http import (
    compose_http_config_path,
    get_http_config_dir,
)
from provisioningserver.utils.fs import atomic_write, get_root_path, snap

log = LegacyLogger()

REGIOND_SOCKET_PATH = os.getenv(
    "MAAS_HTTP_SOCKET_WORKER_BASE_PATH",
    get_maas_data_path("maas-regiond-webapp.sock"),
)


class RegionHTTPService(Service):
    @staticmethod
    def build_unix_socket_path_for_worker(worker_id: str) -> str:
        return f"{REGIOND_SOCKET_PATH}.{worker_id}"

    def __init__(self, postgresListener: PostgresListenerService = None):
        super().__init__()
        self.listener = postgresListener

    @inlineCallbacks
    def startService(self):
        config = yield deferToDatabase(self._getConfiguration)
        self._configure(config)
        yield self._reload_service()
        super().startService()
        if self.listener is not None:
            self.listener.register("sys_reverse_proxy", self._consume_event)

    def stopService(self):
        if self.listener is not None:
            self.listener.unregister("sys_reverse_proxy", self._consume_event)
        return super().stopService()

    def _getConfiguration(self):
        configs = Config.objects.get_configs(
            ("tls_key", "tls_cert", "tls_cacert", "tls_port")
        )
        return _Configuration(
            key=configs["tls_key"],
            cert=configs["tls_cert"],
            cacert=configs["tls_cacert"],
            port=configs["tls_port"],
        )

    def _configure(self, configuration):
        """Update the HTTP configuration for the region proxy service."""
        template = load_template("http", "regiond.nginx.conf.template")

        # Load balancing the unix sockets
        worker_socket_paths = [
            self.build_unix_socket_path_for_worker(worker_id)
            for worker_id in WorkersService.get_worker_ids()
        ]

        if configuration.tls_enabled:
            key_path, cert_path = self._create_cert_files(configuration)
        else:
            key_path, cert_path = "", ""
        environ = {
            "http_port": 5240,
            "tls_enabled": configuration.tls_enabled,
            "tls_port": configuration.port,
            "tls_key_path": key_path,
            "tls_cert_path": cert_path,
            "worker_socket_paths": worker_socket_paths,
            "static_dir": str(get_root_path() / "usr/share/maas"),
        }
        rendered = template.substitute(environ).encode()
        target_path = Path(compose_http_config_path("regiond.nginx.conf"))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(rendered, target_path, overwrite=True, mode=0o644)

    def _create_cert_files(self, configuration):
        cert = Certificate.from_pem(
            configuration.key,
            configuration.cert,
            ca_certs_material=configuration.cacert or "",
        )

        certs_dir = Path(get_http_config_dir()) / "certs"
        certs_dir.mkdir(parents=True, exist_ok=True)
        cert_path = certs_dir / "regiond-proxy.pem"
        key_path = certs_dir / "regiond-proxy-key.pem"

        atomic_write(
            cert.fullchain_pem().encode(),
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
        return key_path, cert_path

    @inlineCallbacks
    def _reload_service(self):
        if snap.running_in_snap():
            service_monitor.restartService("reverse_proxy")
        else:
            service_monitor.reloadService("reverse_proxy")
        yield deferToDatabase(
            certificate_expiration_check.check_tls_certificate
        )

    @inlineCallbacks
    def _consume_event(self, channel, message):
        yield self.stopService()
        yield self.startService()


@dataclass
class _Configuration:
    """Configuration for the region's nginx reverse proxy service."""

    key: Optional[str] = None
    cert: Optional[str] = None
    cacert: Optional[str] = None
    port: Optional[int] = None

    @property
    def tls_enabled(self) -> bool:
        return all((self.port, self.key, self.cert))
