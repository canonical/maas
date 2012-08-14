# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Handling of MAAS API credentials.

The API client deals with credentials consisting of 3 elements: consumer
key, resource token, and resource secret.  These are in OAuth, but the
consumer secret is hardwired to the empty string.

Credentials are represented internally as tuples of these three elements,
but can also be converted to a colon-separated string format for easy
transport between processes.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'convert_string_to_tuple',
    'convert_tuple_to_string',
    ]


def convert_tuple_to_string(creds_tuple):
    """Represent a MAAS API credentials tuple as a colon-separated string."""
    if len(creds_tuple) != 3:
        raise ValueError(
            "Credentials tuple does not consist of 3 elements as expected; "
            "it contains %d."
            % len(creds_tuple))
    return ':'.join(creds_tuple)


def convert_string_to_tuple(creds_string):
    """Recreate a MAAS API credentials tuple from a colon-separated string."""
    creds_tuple = tuple(creds_string.split(':'))
    if len(creds_tuple) != 3:
        raise ValueError(
            "Malformed credentials string.  Expected 3 colon-separated items, "
            "got %r."
            % creds_string)
    return creds_tuple
