# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""keys-related utilities."""

__all__ = [
    'get_protocol_keys',
    ]

from maasserver.enum import KEYS_PROTOCOL_TYPE
import requests


class ImportSSHKeysError(Exception):
    """Importing SSH Keys failed."""


def get_protocol_keys(protocol, auth_id):
    """Retrieve SSH Keys for auth_id using protocol."""
    try:
        if protocol == KEYS_PROTOCOL_TYPE.LP:
            return get_launchpad_ssh_keys(auth_id)
        elif protocol == KEYS_PROTOCOL_TYPE.GH:
            return get_github_ssh_keys(auth_id)
    except requests.exceptions.RequestException as e:
        raise ImportSSHKeysError(e)


def get_launchpad_ssh_keys(auth_id):
    """Retrieve SSH Keys from launchpad."""
    url = 'https://launchpad.net/~%s/+sshkeys' % auth_id
    response = requests.get(url)
    # If HTTP error, need to force the raise
    response.raise_for_status()
    return [key for key in response.text.splitlines() if key]


def get_github_ssh_keys(auth_id):
    """Retrieve SSH Keys from github."""
    url = 'https://api.github.com/users/%s/keys' % auth_id
    response = requests.get(url)
    # If HTTP error, need to force the raise
    response.raise_for_status()
    # github returns JSON content
    return [data['key'] for data in response.json() if 'key' in data]
