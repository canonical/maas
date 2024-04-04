# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal service for the region controller."""

import os
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection as django_connection
from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks

from maasserver.config import RegionConfiguration
from maasserver.service_monitor import service_monitor
from maasserver.utils import load_template
from provisioningserver.certificates import get_maas_cluster_cert_paths
from provisioningserver.logger import get_maas_logger
from provisioningserver.path import get_maas_data_path
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.fs import atomic_write, snap

maaslog = get_maas_logger()


class RegionTemporalService(Service):
    def startService(self):
        self._configure()
        super().startService()

    def _configure(self):
        """Update the Temporal configuration for the Temporal service."""
        template = load_template("temporal", "production.yaml.template")
        dynamic_template = load_template(
            "temporal", "production-dynamic.yaml.template"
        )

        # Can't use the public attribute since it hits
        # maasserver.utils.orm.DisabledDatabaseConnection
        dbconf = settings.DATABASES[django_connection._alias]

        connection_attributes = {}
        host = dbconf["HOST"]
        if host.startswith("/"):
            connection_attributes["host"] = host

            # If the host name starts with @, it is taken as a Unix-domain socket
            # in the abstract namespace (currently supported on Linux and Windows).
            # https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS
            host = "@"

        maas_id = MAAS_ID.get() or "NO_ID"
        application_name = f"maas-temporal-{maas_id}"
        connection_attributes["application_name"] = application_name

        with RegionConfiguration.open() as config:
            broadcast_address = config.broadcast_address

        if not broadcast_address:
            try:
                broadcast_address = self.get_broadcast_address(config.maas_url)
            except Exception as e:
                maaslog.error(
                    f"Failed to identify broadcast address due to: {e}"
                    f"Please consider setting it manually using regiond.conf"
                )

        temporal_config_dir = Path(
            os.environ.get(
                "MAAS_TEMPORAL_CONFIG_DIR", get_maas_data_path("temporal")
            )
        )
        temporal_config_dir.mkdir(parents=True, exist_ok=True)

        cert_file, key_file, cacert_file = get_maas_cluster_cert_paths()

        environ = {
            "database": dbconf["NAME"],
            "user": dbconf.get("USER", ""),
            "password": dbconf.get("PASSWORD", ""),
            "address": f"{host}:{dbconf['PORT']}",
            "connect_attributes": connection_attributes,
            "broadcast_address": broadcast_address,
            "config_dir": str(temporal_config_dir),
            "cert_file": cert_file,
            "key_file": key_file,
            "cacert_file": cacert_file,
        }

        rendered_template = template.substitute(environ).encode()
        rendered_dynamic_template = dynamic_template.substitute(
            environ
        ).encode()

        atomic_write(
            rendered_template,
            temporal_config_dir / "production.yaml",
            overwrite=True,
            mode=0o600,
        )

        atomic_write(
            rendered_dynamic_template,
            temporal_config_dir / "production-dynamic.yaml",
            overwrite=True,
            mode=0o600,
        )

    @inlineCallbacks
    def _reload_service(self):
        if snap.running_in_snap():
            yield service_monitor.restartService("temporal")
        else:
            yield service_monitor.reloadService("temporal")

    def get_broadcast_address(self, maas_url):
        parsed = urlparse(maas_url)
        maas_ip = socket.gethostbyname(parsed.hostname)

        output = subprocess.getoutput(f"ip route get {maas_ip}")
        # root@maas:~# ip route get 10.0.0.37
        # local 10.0.0.37 dev lo src 10.0.0.37 uid 0
        # cache <local>
        return output.split("src ")[1].split()[0]
