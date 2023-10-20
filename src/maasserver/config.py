# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration for the MAAS region."""


from formencode.validators import Int

from provisioningserver.config import (
    Configuration,
    ConfigurationFile,
    ConfigurationMeta,
    ConfigurationOption,
)
from provisioningserver.utils.config import (
    ExtendedURL,
    OneWayStringBool,
    UnicodeString,
)
from provisioningserver.utils.env import MAAS_ID


def get_db_creds_vault_path():
    node_id = MAAS_ID.get()
    assert node_id, f"MAAS ID not set in {MAAS_ID.path}"
    return f"controller/{node_id}/database-creds"


class RegionConfigurationMeta(ConfigurationMeta):
    """Local meta-configuration for the MAAS region."""

    envvar = "MAAS_REGION_CONFIG"
    default = "/etc/maas/regiond.conf"
    backend = ConfigurationFile


class RegionConfiguration(Configuration, metaclass=RegionConfigurationMeta):
    """Local configuration for the MAAS region."""

    maas_url = ConfigurationOption(
        "maas_url",
        "The HTTP URL for the MAAS region.",
        ExtendedURL(
            require_tld=False, if_missing="http://localhost:5240/MAAS"
        ),
    )

    # TODO: This should be considered a fallback scenario
    # MAAS should automatically find reachable IP address and use it.
    membership_address = ConfigurationOption(
        "membership_address",
        "IPv4 address used for communication between Region controllers",
        UnicodeString(if_missing="127.0.0.1", accept_python=False),
    )

    # Database options.
    database_host = ConfigurationOption(
        "database_host",
        "The address of the PostgreSQL database.",
        UnicodeString(if_missing="localhost", accept_python=False),
    )
    database_port = ConfigurationOption(
        "database_port",
        "The port of the PostgreSQL database.",
        Int(if_missing=5432, accept_python=False, min=1, max=65535),
    )
    database_name = ConfigurationOption(
        "database_name",
        "The name of the PostgreSQL database.",
        UnicodeString(if_missing="maasdb", accept_python=False),
    )
    database_user = ConfigurationOption(
        "database_user",
        "The user to connect to PostgreSQL as.",
        UnicodeString(if_missing="maas", accept_python=False),
    )
    database_pass = ConfigurationOption(
        "database_pass",
        "The password for the PostgreSQL user.",
        UnicodeString(if_missing="", accept_python=False),
    )
    database_conn_max_age = ConfigurationOption(
        "database_conn_max_age",
        "The lifetime of a database connection, in seconds.",
        Int(if_missing=(5 * 60), accept_python=False, min=0),
    )
    database_keepalive = ConfigurationOption(
        "database_keepalive",
        "Whether keepalive for database connections is enabled.",
        OneWayStringBool(if_missing=True),
    )
    database_keepalive_idle = ConfigurationOption(
        "database_keepalive_idle",
        "Time (in seconds) after which keepalives will be started.",
        Int(if_missing=15),
    )
    database_keepalive_interval = ConfigurationOption(
        "database_keepalive_interval",
        "Interval (in seconds) between keepalives.",
        Int(if_missing=15),
    )
    database_keepalive_count = ConfigurationOption(
        "database_keepalive_count",
        "Number of keeaplives that can be lost before connection is reset.",
        Int(if_missing=2),
    )

    # Vault options.
    vault_url = ConfigurationOption(
        "vault_url",
        "URL for the Vault server to connect to",
        UnicodeString(if_missing="", accept_python=False),
    )
    vault_secrets_mount = ConfigurationOption(
        "vault_secrets_mount",
        "mount path for the Vault KV engine",
        UnicodeString(if_missing="secret", accept_python=False),
    )
    vault_secrets_path = ConfigurationOption(
        "vault_secrets_path",
        "path prefix for the MAAS secrets stored in Vault KV engine",
        UnicodeString(if_missing="", accept_python=False),
    )
    vault_approle_id = ConfigurationOption(
        "vault_approle_id",
        "Approle ID for Vault authentication",
        UnicodeString(if_missing="", accept_python=False),
    )
    vault_secret_id = ConfigurationOption(
        "vault_secret_id",
        "Secret ID for Vault authentication",
        UnicodeString(if_missing="", accept_python=False),
    )

    # Worker options.
    num_workers = ConfigurationOption(
        "num_workers",
        "The number of regiond worker process to run.",
        Int(if_missing=4, accept_python=False, min=1),
    )

    # Debug options.
    debug = ConfigurationOption(
        "debug",
        "Enable debug mode for detailed error and log reporting.",
        OneWayStringBool(if_missing=False),
    )
    debug_queries = ConfigurationOption(
        "debug_queries",
        "Enable query debugging. Reports number of queries and time for all "
        "actions performed. Requires debug to also be True. mode for detailed "
        "error and log reporting.",
        OneWayStringBool(if_missing=False),
    )
    debug_http = ConfigurationOption(
        "debug_http",
        "Enable HTTP debugging. Logs all HTTP requests and HTTP responses.",
        OneWayStringBool(if_missing=False),
    )
