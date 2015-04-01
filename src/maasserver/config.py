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
    'is_dev_environment',
    'get_region_variable',
    'set_region_variable',
]

import os

from formencode.validators import UnicodeString
from provisioningserver.config import (
    Configuration,
    ConfigurationFile,
    ConfigurationMeta,
    ConfigurationOption,
    ExtendedURL,
)

# Other constants not in the config file
REGIOND_DB_STATIC_ROUTE = '/usr/share/maas/web/static/'

# List of configuration keys


class REGION_CONFIG:
    DB_maas_url = 'maas_url'
    DB_password = 'database_pass'
    DB_username = 'database_user'
    DB_name = 'database_name'
    DB_host = 'database_host'


class RegionConfiguration(Configuration):
    """Local configuration for the MAAS region."""

    class __metaclass__(ConfigurationMeta):
        envvar = "MAAS_REGION_CONFIG"
        default = "/etc/maas/regiond.conf"
        backend = ConfigurationFile

    maas_url = ConfigurationOption(
        "maas_url", "The HTTP URL for the MAAS region.",
        ExtendedURL(require_tld=False,
                    if_missing="http://localhost:5240/MAAS"))

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

"""
This module is responsible for interaction with the region
controller's RegionConfiguration store

"""


def is_dev_environment():
    return os.getenv('DJANGO_SETTINGS_MODULE') == 'maas.development'


def get_region_variable(var):
    """Obtain the given environment variable from regiond.db"""
    with RegionConfiguration.open() as config:
        return getattr(config, var)


def set_region_variable(var, value):
    """ Set the given environment variable in regiond.db"""
    with RegionConfiguration.open() as config:
        setattr(config, var, value)
