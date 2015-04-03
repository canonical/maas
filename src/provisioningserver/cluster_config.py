# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Accessors for cluster configuration as set in `maas_cluster.conf`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'get_cluster_uuid',
    'get_maas_url',
    "get_cluster_variable",
    "get_config_cluster_variable",
    "set_config_cluster_variable", ]

from os import environ

from provisioningserver.config import ClusterConfiguration

# List of configuration keys


class CLUSTER_CONFIG:
    DB_cluster_uuid = 'cluster_uuid'
    DB_maas_url = 'maas_url'
    DB_tftp_resource_root = "tftp_root"
    DB_boot_resources_storage = "tftp_root"
    DB_tftpport = 'tftp_port'


# New get function for ClusterConfiguration backend
def get_config_cluster_variable(var):
    """Obtain the given environment variable from clusterd config"""
    with ClusterConfiguration.open() as config:
        return getattr(config, var)


# Set function for ClusterConfiguration backend
def set_config_cluster_variable(var, value):
    """Set the given environment variable in clusterd config"""
    with ClusterConfiguration.open() as config:
        setattr(config, var, value)


def get_tftp_generator():
    """Return the `tftp_generator` setting, which is
       <maas url>/api/1.0/pxeconfig/
    """
    return '/'.join(get_cluster_variable(CLUSTER_CONFIG.DB_maas_url),
                    'api', '1.0', 'pxeconfig')


# Old get function for config file (via env variables) backend,
# to be removed in follow-up branch. This branch is a prerequisite branch for
# a follow-up branch, where this function will be removed. Both
# the new and old versions of this function have been included
# in this intermediate branch at the request of the package
# maintainers.
def get_cluster_variable(var):
    """Obtain the given environment variable from maas_cluster.conf.

    If the variable is not set, it probably means that whatever script
    started the current process neglected to run maas_cluster.conf.
    In that case, fail helpfully but utterly.
    """
    value = environ.get(var)
    if value is None:
        raise AssertionError(
            "%s is not set.  This probably means that the script which "
            "started this program failed to source maas_cluster.conf."
            % var)
    return value


def get_cluster_uuid():
    """Return the `CLUSTER_UUID` setting."""
    return get_cluster_variable('CLUSTER_UUID')


def get_maas_url():
    """Return the `MAAS_URL` setting."""
    return get_cluster_variable('MAAS_URL')
