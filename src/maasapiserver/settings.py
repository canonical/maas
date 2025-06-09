# Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
import os
from pathlib import Path

import structlog

from maasserver.config import get_db_creds_vault_path, RegionConfiguration
from maasservicelayer.db import DatabaseConfig
from maasservicelayer.vault.api.models.exceptions import VaultNotFoundException
from maasservicelayer.vault.manager import get_region_vault_manager
from provisioningserver.path import get_maas_data_path

logger = structlog.getLogger()


@dataclass
class Config:
    db: DatabaseConfig | None
    debug: bool = False
    debug_queries: bool = False
    debug_http: bool = False


def api_service_socket_path() -> Path:
    """Return the path of the socket for the service."""
    return Path(
        os.getenv(
            "MAAS_APISERVER_HTTP_SOCKET_PATH",
            get_maas_data_path("apiserver-http.sock"),
        )
    )


def internal_api_service_socket_path() -> Path:
    """Return the path of the socket for the service."""
    return Path(
        os.getenv(
            "MAAS_INTERNALAPISERVER_HTTP_SOCKET_PATH",
            get_maas_data_path("internalapiserver-http.sock"),
        )
    )


async def _get_default_db_config(
    config: RegionConfiguration,
) -> DatabaseConfig:
    """
    Builds a default DSN based on region configuration.
    Adapted from maasserver.djangosettings.settings.
    TODO: refactor original class in order to avoid duplication of code.
    """
    client = get_region_vault_manager()
    # If fetching credentials from vault fails, use credentials from local configuration.
    database_user = config.database_user
    database_pass = config.database_pass
    database_name = config.database_name

    # Try fetching vault-stored credentials
    if client is not None:
        try:
            creds = await client.get(get_db_creds_vault_path())
            # Override local configuration
            database_user = creds["user"]
            database_pass = creds["pass"]
            database_name = creds["name"]
        except VaultNotFoundException:
            # Vault does not have DB credentials, but is available. No need to report anything, use local credentials.
            pass
        except Exception as e:
            # Vault entry is unavailable for some reason (misconfigured/sealed/wrong permissions).
            # Report and use local credentials.
            logger.warning(
                "Unable to fetch DB credentials from Vault: ", exc_info=e
            )
            pass

    return DatabaseConfig(
        name=str(database_name),
        host=str(config.database_host),
        username=str(database_user),
        password=str(database_pass),
        port=int(str(config.database_port)),
    )


async def read_config() -> Config:
    try:
        with RegionConfiguration.open() as config:
            database_config = await _get_default_db_config(config)
            debug = config.debug
            debug_queries = debug or config.debug_queries
            debug_http = debug or config.debug_http

    except (FileNotFoundError, KeyError, ValueError):
        # The regiond.conf will attempt to be loaded when the 'maas' command
        # is read by a standard user. We allow this to fail and miss configure the
        # database information. Django will still complain since no 'default'
        # connection is defined.
        database_config = None
        debug = False
        debug_queries = False
        debug_http = False

    return Config(
        db=database_config,
        debug=bool(debug),
        debug_queries=bool(debug_queries),
        debug_http=bool(debug_http),
    )
