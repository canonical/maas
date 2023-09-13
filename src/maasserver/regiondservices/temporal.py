# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal service for the region controller."""

import os
from pathlib import Path
import sys

from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks

from maasserver.service_monitor import service_monitor
from maasserver.utils import load_template
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.path import get_tentative_data_path
from provisioningserver.utils.fs import atomic_write, snap

log = LegacyLogger()


class RegionTemporalService(Service):
    def __init__(self):
        super().__init__()

    @inlineCallbacks
    def startService(self):
        config = yield deferToDatabase(self._getConfiguration)
        self._configure(config)
        yield self._reload_service()
        super().startService()

    def stopService(self):
        return super().stopService()

    def _getConfiguration(self):
        return None

    def _configure(self, configuration):
        """Update the HTTP configuration for the region proxy service."""
        template = load_template("temporal", "production.yaml.template")
        environ = {}
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
