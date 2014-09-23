# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API credentials for node-group workers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_maas_user_gpghome',
    ]

from provisioningserver.path import get_path


def get_maas_user_gpghome():
    """Return the GPG directory for the `maas` user.

    Set $GPGHOME to this value ad-hoc when needed.
    """
    return get_path('/var/lib/maas/gnupg')


cache = {}


# Cache key for the API credentials as last sent by the server.
API_CREDENTIALS_CACHE_KEY = 'api_credentials'


# Cache key for the uuid of the nodegroup that this worker manages.
NODEGROUP_UUID_CACHE_KEY = 'nodegroup_uuid'
