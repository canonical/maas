# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal service for the region controller."""

import os
from pathlib import Path

from django.conf import settings
from django.db import connection as django_connection
from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks

from maasserver.service_monitor import service_monitor
from maasserver.utils import load_template
from provisioningserver.path import get_maas_data_path
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.fs import atomic_write, snap


class RegionTemporalService(Service):
    def startService(self):
        self._configure()
        super().startService()

    def _configure(self):
        """Update the Temporal configuration for the Temporal service."""
        template = load_template("temporal", "production.yaml.template")

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

        environ = {
            "database": dbconf["NAME"],
            "user": dbconf.get("USER", ""),
            "password": dbconf.get("PASSWORD", ""),
            "address": f"{host}:{dbconf['PORT']}",
            "connect_attributes": connection_attributes,
        }

        rendered = template.substitute(environ).encode()

        temporal_config_dir = Path(
            os.environ.get(
                "MAAS_TEMPORAL_CONFIG_DIR", get_maas_data_path("temporal")
            )
        )
        temporal_config_dir.mkdir(parents=True, exist_ok=True)

        atomic_write(
            rendered,
            temporal_config_dir / "production.yaml",
            overwrite=True,
            mode=0o600,
        )

    @inlineCallbacks
    def _reload_service(self):
        if snap.running_in_snap():
            yield service_monitor.restartService("temporal")
        else:
            yield service_monitor.reloadService("temporal")
