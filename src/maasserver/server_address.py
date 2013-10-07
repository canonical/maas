# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper to obtain the MAAS server's address."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_maas_facing_server_address',
    'get_maas_facing_server_host',
    ]


from socket import gethostbyname
from urlparse import urlparse

from django.conf import settings


def get_maas_facing_server_host(nodegroup=None):
    """Return configured MAAS server hostname, for use by nodes or workers.

    :param nodegroup: The nodegroup from the point of view of which the
        server host should be computed.
    :return: Hostname or IP address, as configured in the DEFAULT_MAAS_URL
        setting or as configured on nodegroup.maas_url.
    """
    if nodegroup is None or not nodegroup.maas_url:
        maas_url = settings.DEFAULT_MAAS_URL
    else:
        maas_url = nodegroup.maas_url
    return urlparse(maas_url).hostname


def get_maas_facing_server_address(nodegroup=None):
    """Return address where nodes and workers can reach the MAAS server.

    The address is taken from DEFAULT_MAAS_URL or nodegroup.maas_url.

    :param nodegroup: The nodegroup from the point of view of which the
        server address should be computed.
    :return: An IP address.  If the configured URL uses a hostname, this
        function will resolve that hostname.
    """
    return gethostbyname(get_maas_facing_server_host(nodegroup))
