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
    "AuthenticationFailed",
    "CannotConfigureDHCP",
    "CannotCreateHostMap",
    "CannotRegisterCluster",
    "CannotRemoveHostMap",
    "CommissionNodeFailed",
    "NoConnectionsAvailable",
    "NodeAlreadyExists",
    "NodeStateViolation",
    "NoIPFoundForMACAddress",
    "NoSuchCluster",
    "NoSuchEventType",
    "NoSuchNode",
    "NoSuchOperatingSystem",
    "PowerActionAlreadyInProgress",
    "RegistrationFailed",
]


class NoConnectionsAvailable(Exception):
    """There is no connection available."""

    def __init__(self, message='', uuid=None):
        super(NoConnectionsAvailable, self).__init__(message)
        self.uuid = uuid


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

    @classmethod
    def from_mac_address(cls, mac_address):
        return cls(
            "Node with mac_address=%s could not be found." % mac_address
        )


class NodeStateViolation(Exception):
    """The specified state transition cannot be performed."""


class NoSuchCluster(Exception):
    """The specified cluster was not found."""

    @classmethod
    def from_uuid(cls, uuid):
        return cls(
            "The cluster with UUID %s could not "
            "be found." % uuid
        )


class NoSuchOperatingSystem(Exception):
    """The specified OS was not found."""


class CommissionNodeFailed(Exception):
    """Failure to commission node."""


class CannotConfigureDHCP(Exception):
    """Failure while configuring a DHCP server."""


class CannotCreateHostMap(Exception):
    """The host map could not be created."""


class CannotRemoveHostMap(Exception):
    """The host map could not be removed."""


class NodeAlreadyExists(Exception):
    """A node already exists with a given MAC address."""


class NoIPFoundForMACAddress(Exception):
    """No IP was found for a given MAC address."""


class PowerActionAlreadyInProgress(Exception):
    """A power action was requested on a node where a power action is
    already in progress.
    """


class CannotRegisterCluster(Exception):
    """The cluster could not be registered."""

    @classmethod
    def from_uuid(cls, uuid, message):
        return cls(
            "The cluster with UUID %s could not "
            "be registered:\n%s" % (uuid, message)
        )


class AuthenticationFailed(Exception):
    """One or both sides of the connection failed to authenticate."""


class RegistrationFailed(Exception):
    """The region did not or was not able to register the cluster."""
