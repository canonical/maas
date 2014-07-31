# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to network and cluster interfaces."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'make_name_from_interface',
    ]

from random import randint
import re


def make_name_from_interface(interface):
    """Generate a cluster interface name based on a network interface name.

    The name is used as an identifier in API URLs, so awkward characters are
    not allowed: whitespace, colons, etc.  If the interface name had any such
    characters in it, they are replaced with a double dash (`--`).

    If `interface` is `None`, or empty, a name will be made up.
    """
    if interface is None or interface == u'':
        base_name = u'unnamed-%d' % randint(1000000, 9999999)
    else:
        base_name = interface
    return re.sub(u'[^\w:.-]', '--', base_name)
