# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration for the MAAS region."""

__all__ = [
    "RegionConfiguration",
]

from os import path

from provisioningserver.config import (
    Configuration,
    ConfigurationFile,
    ConfigurationMeta,
    ConfigurationOption,
    is_dev_environment,
)
from provisioningserver.utils.config import (
    ExtendedURL,
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
        "maas_url", "The HTTP URL for the MAAS region.", ExtendedURL(
            require_tld=False, if_missing="http://localhost:5240/MAAS"))

    # Database options.
    database_host = ConfigurationOption(
        "database_host", "The address of the PostgreSQL database.",
        UnicodeString(if_missing="localhost", accept_python=False))
    database_name = ConfigurationOption(
        "database_name", "The name of the PostgreSQL database.",
        UnicodeString(if_missing="maasdb", accept_python=False))
    database_user = ConfigurationOption(
        "database_user", "The user to connect to PostgreSQL as.",
        UnicodeString(if_missing="maas", accept_python=False))
    database_pass = ConfigurationOption(
        "database_pass", "The password for the PostgreSQL user.",
        UnicodeString(if_missing="", accept_python=False))

    @property
    def static_root(self):
        """The filesystem path for static content.

        In production this setting is set to the path where the static files
        are located on the filesystem.

        In the development environment the STATIC_ROOT setting is not set, so
        return the relative path to the static files from this files location.
        """
        if is_dev_environment():
            return path.join(path.dirname(__file__), "static")
        else:
            return "/usr/share/maas/web/static"
