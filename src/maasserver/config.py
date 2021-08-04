# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration for the MAAS region."""


import os

from formencode.validators import Int, Number

from provisioningserver.config import (
    Configuration,
    ConfigurationFile,
    ConfigurationMeta,
    ConfigurationOption,
)
from provisioningserver.path import get_maas_data_path
from provisioningserver.utils.config import (
    DirectoryString,
    ExtendedURL,
    OneWayStringBool,
    UnicodeString,
)


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
        "Interval (in seconds) between keepaliveds.",
        Int(if_missing=15),
    )
    database_keepalive_count = ConfigurationOption(
        "database_keepalive_count",
        "Number of keeaplives that can be lost before connection is reset.",
        Int(if_missing=2),
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

    # TFTP options.
    tftp_port = ConfigurationOption(
        "tftp_port",
        "The UDP port on which to listen for TFTP requests.",
        Number(min=0, max=(2 ** 16) - 1, if_missing=6969),  # proxied by rack
    )
    tftp_root = ConfigurationOption(
        "tftp_root",
        "The root directory for TFTP resources.",
        DirectoryString(
            # Don't validate values that are already stored.
            accept_python=True,
            if_missing=get_maas_data_path("boot-resources/current"),
        ),
    )

    # GRUB options.

    @property
    def grub_root(self):
        "The root directory for GRUB resources."
        return os.path.join(self.tftp_root, "grub")
