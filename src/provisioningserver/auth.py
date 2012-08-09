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
    'record_api_credentials',
    ]

# API credentials as last sent by the server.  The worker uses these
# credentials to access the MAAS API.
# Shared between threads.
recorded_api_credentials = None


def record_api_credentials(api_credentials):
    """Update the recorded API credentials.

    :param api_credentials: Newly received API credentials, in the form of
        a single string: consumer key, resource token, and resource seret
        separated by colons.
    """
    global recorded_api_credentials
    recorded_api_credentials = api_credentials


def get_recorded_api_credentials():
    """Return API credentials as last received from the server.

    :return: If credentials have been received, a tuple of
        (consumer_key, resource_token, resource_secret) as expected by
        :class:`MAASOauth`.  Otherwise, None.
    """
    credentials_string = recorded_api_credentials
    if credentials_string is None:
        return None
    else:
        return tuple(credentials_string.split(':'))
