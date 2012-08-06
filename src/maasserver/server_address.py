# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper to obtain the MAAS server's address."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'get_maas_facing_server_address',
    'get_maas_facing_server_host',
    ]


from socket import gethostbyname
from urlparse import urlparse

from django.conf import settings


def get_maas_facing_server_host():
    """Return configured MAAS server hostname, for use by nodes or workers.

    :return: Hostname or IP address, exactly as configured in the
        DEFAULT_MAAS_URL setting.
    """
    return urlparse(settings.DEFAULT_MAAS_URL).hostname


def get_maas_facing_server_address():
    """Return address where nodes and workers can reach the MAAS server.

    The address is taken from DEFAULT_MAAS_URL, which in turn is based on the
    server's primary IP address by default, but can be overridden for
    multi-interface servers where this guess is wrong.

    :return: An IP address.  If the configured URL uses a hostname, this
        function will resolve that hostname.
    """
    return gethostbyname(get_maas_facing_server_host())
