# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal service for the region controller."""

import os
from pathlib import Path
import sys

from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks

from maasserver.config import RegionConfiguration
from maasserver.djangosettings.settings import _get_default_db_config
from maasserver.service_monitor import service_monitor
from maasserver.utils import load_template
from provisioningserver.logger import LegacyLogger
from provisioningserver.path import get_tentative_data_path
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.fs import atomic_write, snap

log = LegacyLogger()


class RegionTemporalService(Service):
    def __init__(self):
        super().__init__()

    def startService(self):
        self._configure()
        super().startService()

    def stopService(self):
        super().stopService()

    def _configure(self):
        """Update the Temporal configuration for the Temporal service."""
        template = load_template("temporal", "production.yaml.template")

        with RegionConfiguration.open() as config:
            dbconf = _get_default_db_config(config)

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

        target_path = Path(
            os.path.join(get_temporal_config_dir(), "production.yaml")
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(rendered, target_path, overwrite=True, mode=0o644)

    @inlineCallbacks
    def _reload_service(self):
        if snap.running_in_snap():
            yield service_monitor.restartService("temporal")
        else:
            yield service_monitor.reloadService("temporal")


def get_temporal_config_dir():
    """Location of MAAS' Temporal configuration file"""
    setting = os.getenv(
        "MAAS_TEMPORAL_CONFIG_DIR",
        get_tentative_data_path("/var/lib/maas/temporal"),
    )
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        return setting.decode(fsenc)
    else:
        return setting
