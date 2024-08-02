from dataclasses import dataclass
from functools import lru_cache
import logging
import os
from pathlib import Path
from typing import Optional

from maasserver.config import get_db_creds_vault_path, RegionConfiguration
from maasservicelayer.db import DatabaseConfig
from maasservicelayer.vault.api.apiclient import AsyncVaultApiClient
from maasservicelayer.vault.api.models.exceptions import VaultNotFoundException
from maasservicelayer.vault.manager import AsyncVaultManager
from provisioningserver.path import get_maas_data_path

logger = logging.getLogger(__name__)


@dataclass
class Config:
    db: DatabaseConfig | None
    debug_queries: bool = False
    debug: bool = False


def api_service_socket_path() -> Path:
    """Return the path of the socket for the service."""
    return Path(
        os.getenv(
            "MAAS_APISERVER_HTTP_SOCKET_PATH",
            get_maas_data_path("apiserver-http.sock"),
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
            logging.getLogger(__name__).warning(
                "Unable to fetch DB credentials from Vault: ", exc_info=e
            )
            pass

    return DatabaseConfig(
        name=database_name,
        host=config.database_host,
        username=database_user,
        password=database_pass,
        port=config.database_port,
    )


async def read_config() -> Config:
    try:
        with RegionConfiguration.open() as config:
            database_config = await _get_default_db_config(config)
            debug_queries = config.debug_queries
            debug = config.debug
            # XXX: todo check for HTTP debug flags

    except (FileNotFoundError, KeyError, ValueError):
        # The regiond.conf will attempt to be loaded when the 'maas' command
        # is read by a standard user. We allow this to fail and miss configure the
        # database information. Django will still complain since no 'default'
        # connection is defined.
        database_config = None
        debug_queries = False
        debug = False
    return Config(db=database_config, debug_queries=debug_queries, debug=debug)


@lru_cache()
def get_region_vault_manager() -> Optional[AsyncVaultManager]:
    """Return an AsyncVaultManager properly configured according to the region configuration.

    If configuration options for Vault are not set, None is returned.
    """
    with RegionConfiguration.open() as config:
        if not all(
            (config.vault_url, config.vault_approle_id, config.vault_secret_id)
        ):
            return None
        return AsyncVaultManager(
            vault_api_client=AsyncVaultApiClient(base_url=config.vault_url),
            role_id=config.vault_approle_id,
            secret_id=config.vault_secret_id,
            secrets_base_path=config.vault_secrets_path,
            secrets_mount=config.vault_secrets_mount,
        )
