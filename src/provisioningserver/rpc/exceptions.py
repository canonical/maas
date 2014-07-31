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
    "CannotCreateHostMap",
    "CannotRemoveHostMap",
    "NoConnectionsAvailable",
    "NoSuchEventType",
    "NoSuchNode",
    "NoSuchOperatingSystem",
]


class NoConnectionsAvailable(Exception):
    """There is no connection available."""


class NoSuchEventType(Exception):
    """The specified event type was not found."""

    @classmethod
    def from_name(cls, name):
        return cls(
            "Event type with name=%s could not be found." % name
        )


class NoSuchNode(Exception):
    """The specified node was not found."""

    @classmethod
    def from_system_id(cls, system_id):
        return cls(
            "Node with system_id=%s could not be found." % system_id
        )


class NoSuchOperatingSystem(Exception):
    """The specified OS was not found."""


class CannotCreateHostMap(Exception):
    """The host map could not be created."""


class CannotRemoveHostMap(Exception):
    """The host map could not be removed."""
