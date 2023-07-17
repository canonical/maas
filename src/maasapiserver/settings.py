from dataclasses import dataclass
import logging
import os
from pathlib import Path
from urllib.parse import urlencode

from maasserver.config import get_db_creds_vault_path, RegionConfiguration
from maasserver.vault import (
    get_region_vault_client,
    UnknownSecretPath,
    VaultError,
)
from provisioningserver.path import get_maas_data_path


@dataclass
class DatabaseConfig:
    name: str
    host: str
    username: str | None = None
    password: str | None = None
    port: int | None = None

    @property
    def dsn(self) -> str:
        params = {
            "host": self.host,
            "user": self.username,
            "password": self.password,
            "port": self.port,
        }
        for key, value in list(params.items()):
            if value is None:
                del params[key]
        return f"postgresql+asyncpg:///{self.name}?{urlencode(params)}"


@dataclass
class Config:
    db: DatabaseConfig | None
    debug_queries: bool = False


def api_service_socket_path() -> Path:
    """Return the path of the socket for the service."""
    return Path(
        os.getenv(
            "MAAS_APISERVER_HTTP_SOCKET_PATH",
            get_maas_data_path("apiserver-http.sock"),
        )
    )


def _get_default_db_config(config: RegionConfiguration) -> DatabaseConfig:
    """
    Builds a default DSN based on region configuration.
    Adapted from maasserver.djangosettings.settings.
    TODO: refactor original class in order to avoid duplication of code.
    """
    client = get_region_vault_client()
    # If fetching credentials from vault fails, use credentials from local configuration.
    database_user = config.database_user
    database_pass = config.database_pass
    database_name = config.database_name

    # Try fetching vault-stored credentials
    if client is not None:
        try:
            creds = client.get(get_db_creds_vault_path())
            # Override local configuration
            database_user = creds["user"]
            database_pass = creds["pass"]
            database_name = creds["name"]
        except UnknownSecretPath:
            # Vault does not have DB credentials, but is available. No need to report anything, use local credentials.
            pass
        except VaultError as e:
            # Vault entry is unavailable for some reason (misconfigured/sealed/wrong permissions).
            # Report and use local credentials.
            logging.getLogger(__name__).warning(
                "Unable to fetch DB credentials from Vault: ", exc_info=e
            )
            pass

    return DatabaseConfig(
        database_name,
        config.database_host,
        database_user,
        database_pass,
        config.database_port,
    )


def read_db_config() -> Config:
    try:
        with RegionConfiguration.open() as config:
            database_config = _get_default_db_config(config)
            debug_queries = config.debug_queries
            # XXX: todo check for general debug and HTTP debug flags

    except (FileNotFoundError, KeyError, ValueError):
        # The regiond.conf will attempt to be loaded when the 'maas' command
        # is read by a standard user. We allow this to fail and miss configure the
        # database information. Django will still complain since no 'default'
        # connection is defined.
        database_config = None
        debug_queries = False
    return Config(db=database_config, debug_queries=debug_queries)
