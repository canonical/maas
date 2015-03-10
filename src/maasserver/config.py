# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration for the MAAS region."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "RegionConfiguration",
    ]

from formencode.validators import (
    UnicodeString,
    URL,
    )
from provisioningserver.config import (
    Configuration,
    ConfigurationMeta,
    ConfigurationOption,
    )


class RegionConfiguration(Configuration):
    """Local configuration for the MAAS region."""

    class __metaclass__(ConfigurationMeta):
        envvar = "MAAS_REGION_CONFIG"
        default = "/var/lib/maas/region.db"

    maas_url = ConfigurationOption(
        "maas_url", "The HTTP URL for the MAAS region.",
        URL(require_tld=False, if_missing="http://localhost:5240/MAAS"))

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
