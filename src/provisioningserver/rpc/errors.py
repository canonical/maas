# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Errors arising from the RPC system."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "NoConnectionsAvailable",
]


class NoConnectionsAvailable(Exception):
    """There is no connection available."""
