# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API credentials for node-group workers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'get_recorded_api_credentials',
    'get_recorded_nodegroup_name',
    'get_recorded_maas_url',
    'record_api_credentials',
    'record_nodegroup_name',
    ]

from apiclient.creds import convert_string_to_tuple
from provisioningserver import cache

# Cache key for URL to the central MAAS server.
MAAS_URL_CACHE_KEY = 'maas_url'

# Cache key for the API credentials as last sent by the server.
API_CREDENTIALS_CACHE_KEY = 'api_credentials'

# Cache key for the name of the nodegroup that this worker manages.
NODEGROUP_NAME_CACHE_KEY = 'nodegroup_name'


def record_maas_url(maas_url):
    """Record the MAAS server URL as sent by the server."""
    cache.cache.set(MAAS_URL_CACHE_KEY, maas_url)


def get_recorded_maas_url():
    """Return the base URL for the MAAS server."""
    return cache.cache.get(MAAS_URL_CACHE_KEY)


def record_api_credentials(api_credentials):
    """Update the recorded API credentials.

    :param api_credentials: Newly received API credentials, in the form of
        a single string: consumer key, resource token, and resource seret
        separated by colons.
    """
    cache.cache.set(API_CREDENTIALS_CACHE_KEY, api_credentials)


def get_recorded_api_credentials():
    """Return API credentials as last received from the server.

    :return: If credentials have been received, a tuple of
        (consumer_key, resource_token, resource_secret) as expected by
        :class:`MAASOauth`.  Otherwise, None.
    """
    credentials_string = cache.cache.get(API_CREDENTIALS_CACHE_KEY)
    if credentials_string is None:
        return None
    else:
        return convert_string_to_tuple(credentials_string)


def record_nodegroup_name(nodegroup_name):
    """Record the name of the nodegroup we manage, as sent by the server."""
    cache.cache.set(NODEGROUP_NAME_CACHE_KEY, nodegroup_name)


def get_recorded_nodegroup_name():
    """Return the name of this worker's nodegroup, as sent by the server.

    If the server has not sent the name yet, returns None.
    """
    return cache.cache.get(NODEGROUP_NAME_CACHE_KEY)
