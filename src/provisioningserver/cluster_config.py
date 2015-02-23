# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    'set_cluster_uuid'
    'get_boot_resources_storage'
    'get_tftp_resource_root'
    'get_tftp_port'
    'get_tftp_generator'
    ]

import os

# NOTE! NOTE NOTE!
#
# DUPLICATING THESE IN TWO PLACES FOR THE MOMENT UNTIL A SIGNLE LOCATION IS SELECTED
#
# NOTE! NOTE NOTE!

CLUSTERD_DB_PATH = '/var/lib/maas/clusterd.db'
CLUSTERD_DB_cluster_uuid = 'CLUSTER_UUID'
CLUSTERD_DB_maas_url = 'MAAS_URL'
CLUSTERD_DB_tftp_resource_root = "resource_root"
CLUSTERD_DB_tftpport = 'tftpport'


def get_cluster_variable(var):
    """Obtain the given environment variable from maas_cluster.conf.

    If the variable is not set, it probably means that whatever script
    started the current process neglected to run maas_cluster.conf.
    In that case, fail helpfully but utterly.
    """
    value = None
    from maascli.config import ProfileConfig
    with ProfileConfig.open(CLUSTERD_DB_PATH) as config:
        value = config[var]

    if value is None:
        raise AssertionError(
            "%s is not set.  This probably means that the script which "
            "started this program failed to source maas_cluster.conf."
            % var)
    return value


def get_cluster_uuid():
    """Return the `cluster uuid` setting."""
    return get_cluster_variable(CLUSTERD_DB_cluster_uuid)


def get_maas_url():
    """Return the `maas url` setting."""
    return get_cluster_variable(CLUSTERD_DB_maas_url)


def set_cluster_variable(var, value):
    from maascli.config import ProfileConfig
    with ProfileConfig.open(CLUSTERD_DB_PATH) as config:
        config[var] = value

def set_cluster_uuid(value):
    set_cluster_variable(CLUSTERD_DB_cluster_uuid, value)


def get_boot_resources_storage():
    """Return the `get_boot_resources_storage` setting."""
    return get_cluster_variable(CLUSTERD_DB_tftp_resource_root)


def get_tftp_resource_root():
    """Return the `get_tftp_resource_root` setting."""
    return get_cluster_variable(CLUSTERD_DB_tftp_resource_root)


def get_tftp_port():
    """Return the `get_tftp_port` setting."""
    return get_cluster_variable(CLUSTERD_DB_tftpport)


def get_tftp_generator():
    """Return the `get_tftp_generator` setting, which is maas url/api/1.0/pxeconfig/"""
    return os.path.join(get_maas_url(), 'api' , '1.0', 'pxeconfig')