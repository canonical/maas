# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Errors arising from the RPC system."""


class NoConnectionsAvailable(Exception):
    """There is no connection available."""

    def __init__(self, message="", uuid=None):
        super().__init__(message)
        self.uuid = uuid


class AllConnectionsBusy(Exception):
    """The current connection pool is busy"""


class MaxConnectionsOpen(Exception):
    """The maxmimum number of connections are currently open"""


class NoSuchEventType(Exception):
    """The specified event type was not found."""

    @classmethod
    def from_name(cls, name):
        return cls("Event type with name=%s could not be found." % name)


class NoSuchNode(Exception):
    """The specified node was not found."""

    @classmethod
    def from_system_id(cls, system_id):
        return cls("Node with system_id=%s could not be found." % system_id)

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
            "The rack controller with UUID %s could not be found." % uuid
        )


class NoSuchOperatingSystem(Exception):
    """The specified OS was not found."""


class CommissionNodeFailed(Exception):
    """Failure to commission node."""


class CannotConfigureDHCP(Exception):
    """Failure while configuring a DHCP server."""


class CannotCreateHostMap(Exception):
    """The host map could not be created."""


class CannotModifyHostMap(Exception):
    """The host map could not be modified."""


class CannotRemoveHostMap(Exception):
    """The host map could not be removed."""


class NodeAlreadyExists(Exception):
    """A node already exists with a given MAC address."""


class NoIPFoundForMACAddress(Exception):
    """No IP was found for a given MAC address."""


class PowerActionFail(Exception):
    """Raised when there's a problem executing a power script."""


class UnknownPowerType(Exception):
    """Raised when trying to process an unknown power type."""


class UnknownPodType(Exception):
    """Raised when trying to process an unknown pod type."""


class PodActionFail(Exception):
    """Raised when performing a pod action."""


class PodInvalidResources(Exception):
    """Raised when a pod cannot compose a machine because of
    invalid resources."""


class CannotRegisterCluster(Exception):
    """The cluster could not be registered."""

    @classmethod
    def from_uuid(cls, uuid, message):
        return cls(
            "The rack controller with UUID %s could not "
            "be registered:\n%s" % (uuid, message)
        )


class CannotRegisterRackController(Exception):
    """The rack controller could not be registered."""


class AuthenticationFailed(Exception):
    """One or both sides of the connection failed to authenticate."""


class RegistrationFailed(Exception):
    """The region did not or was not able to register the cluster."""


class BootConfigNoResponse(Exception):
    """The region gave no response for the boot configuration."""


class CannotDisableAndShutoffRackd(Exception):
    """Rackd cannot be disabled and shutoff."""


class ScanNetworksAlreadyInProgress(Exception):
    """Already scanning all networks; request ignored."""


class NoSuchScope(Exception):
    """The scope for controller state update is unknown."""
