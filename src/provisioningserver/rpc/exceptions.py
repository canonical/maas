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
    "NoSuchNode",
    "NoSuchOperatingSystem",
]


class NoConnectionsAvailable(Exception):
    """There is no connection available."""


class NoSuchNode(Exception):
    """The specified node was not found."""

    @classmethod
    def from_system_id(cls, system_id):
        return cls(
            "Node with system_id=%s could not be found." % system_id
        )


class NoSuchOperatingSystem(Exception):
    """The specified OS was not found."""
