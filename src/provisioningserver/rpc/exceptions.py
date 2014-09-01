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
    "CannotConfigureDHCP",
    "CannotCreateHostMap",
    "CannotRemoveHostMap",
    "MultipleFailures",
    "NoConnectionsAvailable",
    "NoSuchCluster",
    "NoSuchEventType",
    "NoSuchNode",
    "NoSuchOperatingSystem",
]

from twisted.python.failure import Failure


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


class NoSuchCluster(Exception):
    """The specified cluster (a.k.a. node-group) was not found."""

    @classmethod
    def from_uuid(cls, uuid):
        return cls(
            "The cluster (a.k.a. node-group) with UUID %s could not "
            "be found." % uuid
        )


class NoSuchOperatingSystem(Exception):
    """The specified OS was not found."""


class CannotConfigureDHCP(Exception):
    """Failure while configuring a DHCP server."""


class CannotCreateHostMap(Exception):
    """The host map could not be created."""


class CannotRemoveHostMap(Exception):
    """The host map could not be removed."""


class MultipleFailures(Exception):
    """Represents multiple failures.

    Each argument is a :py:class:`twisted.python.failure.Failure` instance. A
    new one of these can be created when in an exception handler simply by
    instantiating a new `Failure` instance without arguments.
    """

    def __init__(self, *failures):
        for failure in failures:
            if not isinstance(failure, Failure):
                raise AssertionError(
                    "All failures must be instances of twisted.python."
                    "failure.Failure, not %r" % (failure,))
        super(MultipleFailures, self).__init__(*failures)
