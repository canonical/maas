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

    # This should be considered a fallback scenario as
    # MAAS should automatically find reachable IP address and use it.
    broadcast_address = ConfigurationOption(
        "broadcast_address",
        "IPv4 address used for communication between Region controllers",
        UnicodeString(if_missing="", accept_python=False),
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

    # Security hardening options.
    hardening_enabled = ConfigurationOption(
        "hardening_enabled",
        "Security hardening activation: 'auto' (on when the host is in FIPS "
        "mode), 'on' (force on), or 'off'.",
        UnicodeString(if_missing="auto"),
    )

    api_bind = ConfigurationOption(
        "api_bind",
        "Address the public API server binds to when hardening is active.",
        UnicodeString(if_missing="0.0.0.0"),
    )
    prometheus_bind = ConfigurationOption(
        "prometheus_bind",
        "Address the Prometheus metrics endpoint binds to.",
        UnicodeString(if_missing=""),
    )
    temporal_bind = ConfigurationOption(
        "temporal_bind",
        "Address the Temporal services bind to.",
        UnicodeString(if_missing=""),
    )
    rpc_bind = ConfigurationOption(
        "rpc_bind",
        "Address the region RPC listener binds to.",
        UnicodeString(if_missing=""),
    )

    database_sslmode = ConfigurationOption(
        "database_sslmode",
        "SSL mode for the PostgreSQL connection (e.g. verify-full, verify-ca).",
        UnicodeString(if_missing="prefer"),
    )
    database_sslcert = ConfigurationOption(
        "database_sslcert",
        "Path to the client TLS certificate for PostgreSQL mTLS.",
        UnicodeString(if_missing=""),
    )
    database_sslkey = ConfigurationOption(
        "database_sslkey",
        "Path to the client TLS key for PostgreSQL mTLS.",
        UnicodeString(if_missing=""),
    )
    database_sslrootcert = ConfigurationOption(
        "database_sslrootcert",
        "Path to the CA certificate for verifying the PostgreSQL server.",
        UnicodeString(if_missing=""),
    )

    api_tls_cert = ConfigurationOption(
        "api_tls_cert",
        "Path to the TLS certificate for the public API endpoint.",
        UnicodeString(if_missing=""),
    )
    api_tls_key = ConfigurationOption(
        "api_tls_key",
        "Path to the TLS private key for the public API endpoint.",
        UnicodeString(if_missing=""),
    )
    api_tls_dhparam = ConfigurationOption(
        "api_tls_dhparam",
        "Path to the DH parameters file for NGINX TLS (optional).",
        UnicodeString(if_missing=""),
    )
    api_rate_limit_rate = ConfigurationOption(
        "api_rate_limit_rate",
        "NGINX rate limit (e.g. '10r/s') applied per client IP.",
        UnicodeString(if_missing="10r/s"),
    )
    api_rate_limit_burst = ConfigurationOption(
        "api_rate_limit_burst",
        "NGINX rate limit burst size.",
        Int(if_missing=20, accept_python=False, min=1),
    )
    api_conn_limit = ConfigurationOption(
        "api_conn_limit",
        "NGINX concurrent connection limit per client IP.",
        Int(if_missing=100, accept_python=False, min=1),
    )
