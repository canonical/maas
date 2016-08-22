# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""keys-related utilities."""

__all__ = [
    'get_protocol_keys',
    ]

from maasserver.enum import KEYS_PROTOCOL_TYPE
import requests


def get_protocol_keys(protocol, auth_id):
    """Return SSH Keys for auth_id using protocol."""
    if protocol == KEYS_PROTOCOL_TYPE.LP:
        url = 'https://launchpad.net/~%s/+sshkeys' % auth_id
    elif protocol == KEYS_PROTOCOL_TYPE.GH:
        url = 'https://api.github.com/users/%s/keys' % auth_id
    response = requests.get(url)
    return response.text.split('\n')
