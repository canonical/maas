# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS CLI authentication."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'obtain_credentials',
    ]

from getpass import getpass
import sys

from apiclient.creds import convert_string_to_tuple


def try_getpass(prompt):
    """Call `getpass`, ignoring EOF errors."""
    try:
        return getpass(prompt)
    except EOFError:
        return None


def obtain_credentials(credentials):
    """Prompt for credentials if possible.

    If the credentials are "-" then read from stdin without interactive
    prompting.
    """
    if credentials == "-":
        credentials = sys.stdin.readline().strip()
    elif credentials is None:
        credentials = try_getpass(
            "API key (leave empty for anonymous access): ")
    # Ensure that the credentials have a valid form.
    if credentials and not credentials.isspace():
        return convert_string_to_tuple(credentials)
    else:
        return None
