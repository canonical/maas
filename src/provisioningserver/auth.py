# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API credentials for node-group workers."""

__all__ = ["get_maas_user_gpghome"]

from provisioningserver.path import get_data_path


def get_maas_user_gpghome():
    """Return the GPG directory for the `maas` user.

    Set $GPGHOME to this value ad-hoc when needed.
    """
    return get_data_path("/var/lib/maas/gnupg")


cache = {}


# Cache key for the API credentials as last sent by the server.
API_CREDENTIALS_CACHE_KEY = "api_credentials"
