# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OpenFGA service for the region controller."""

import os
from pathlib import Path
from urllib.parse import quote, urlunparse

from django.conf import settings
from django.db import connection as django_connection
from twisted.application.service import Service
import yaml

from maascommon.path import get_maas_data_path
from provisioningserver.utils.fs import atomic_write

DEFAULT_MAX_OPEN_CONNS = 3
DEFAULT_MAX_IDLE_CONNS = 1
OPENFGA_CONFIG_NAME = "openfga.yaml"


def build_openfga_dsn(
    host: str, port: int, user: str, password: str, name: str
) -> str:
    """Build a PostgreSQL DSN for the OpenFGA datastore.

    Unix-domain sockets are passed via the ``host`` query parameter; TCP
    connections use the normal netloc form.
    """
    auth = quote(user, safe="")
    if password:
        auth = f"{auth}:{quote(password, safe='')}"

    if host.startswith("/"):
        netloc = f"{auth}@"
        query = f"host={quote(host, safe='')}&search_path=openfga"
    else:
        netloc = f"{auth}@{host}:{port}"
        query = "search_path=openfga"

    return urlunparse(("postgres", netloc, f"/{name}", "", query, ""))


def _get_openfga_config_path() -> Path:
    """Return the path to the OpenFGA configuration file.

    The path can be overridden with ``MAAS_OPENFGA_CONFIG_DIR``; otherwise it
    lives under the MAAS data path.
    """
    config_dir = os.environ.get("MAAS_OPENFGA_CONFIG_DIR")
    if config_dir is None:
        config_dir = get_maas_data_path("")
    return Path(config_dir) / OPENFGA_CONFIG_NAME


class RegionOpenFGAService(Service):
    def startService(self):
        self._configure()
        super().startService()

    def _configure(self):
        """Write the OpenFGA configuration for the OpenFGA service.

        This uses Django's ``DATABASES`` setting, which already resolves
        Vault-stored credentials in Vault-enabled deployments. This mirrors
        the way ``RegionTemporalService._configure`` generates the Temporal
        server configuration.
        """
        dbconf = settings.DATABASES[django_connection._alias]

        dsn = build_openfga_dsn(
            dbconf["HOST"],
            int(dbconf.get("PORT", "5432")),
            dbconf.get("USER", ""),
            dbconf.get("PASSWORD", ""),
            dbconf["NAME"],
        )

        config_path = _get_openfga_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config = {
            "database_uri": dsn,
            "openfga_max_open_conns": DEFAULT_MAX_OPEN_CONNS,
            "openfga_max_idle_conns": DEFAULT_MAX_IDLE_CONNS,
        }

        atomic_write(
            yaml.safe_dump(config).encode("utf-8"),
            config_path,
            overwrite=True,
            mode=0o600,
        )
