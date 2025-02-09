# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API credentials for node-group workers."""

from provisioningserver.path import get_maas_data_path


def get_maas_user_gpghome():
    """Return the GPG directory for the `maas` user.

    Set $GPGHOME to this value ad-hoc when needed.
    """
    return get_maas_data_path("gnupg")


cache = {}


# Cache key for the API credentials as last sent by the server.
API_CREDENTIALS_CACHE_KEY = "api_credentials"
