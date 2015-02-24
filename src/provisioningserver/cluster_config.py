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
    ]

from os import environ


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
