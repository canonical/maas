# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Base pod driver."""

__all__ = [
    "PodActionError",
    "PodAuthError",
    "PodConnError",
    "PodDriver",
    "PodDriverBase",
    "PodError",
    "PodFatalError",
]

from abc import abstractmethod

import attr

from provisioningserver.drivers import (
    IP_EXTRACTOR_SCHEMA,
    SETTING_PARAMETER_FIELD_SCHEMA,
)
from provisioningserver.drivers.power import PowerDriver, PowerDriverBase

# JSON schema for what a pod driver definition should look like.
JSON_POD_DRIVER_SCHEMA = {
    "title": "Pod driver setting set",
    "type": "object",
    "properties": {
        "driver_type": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "fields": {"type": "array", "items": SETTING_PARAMETER_FIELD_SCHEMA},
        "ip_extractor": IP_EXTRACTOR_SCHEMA,
        "queryable": {"type": "boolean"},
        "missing_packages": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["driver_type", "name", "description", "fields"],
}

# JSON schema for multple pod drivers.
JSON_POD_DRIVERS_SCHEMA = {
    "title": "Pod drivers parameters set",
    "type": "array",
    "items": JSON_POD_DRIVER_SCHEMA,
}


class PodError(Exception):
    """Base error for all pod driver failure commands."""


class PodFatalError(PodError):
    """Error that is raised when the pod action should not continue to
    retry at all.

    This exception will cause the pod action to fail instantly,
    without retrying.
    """


class PodAuthError(PodFatalError):
    """Error raised when pod driver fails to authenticate to the pod.

    This exception will cause the pod action to fail instantly,
    without retrying.
    """


class PodConnError(PodError):
    """Error raised when pod driver fails to communicate to the pod."""


class PodActionError(PodError):
    """Error when actually performing an action on the pod, like `compose`
    or `discover`."""


def converter_obj(expected, optional=False):
    """Convert the given value to an object of type `expected`."""

    def converter(value):
        if optional and value is None:
            return None
        if isinstance(value, expected):
            return value
        elif isinstance(value, dict):
            return expected(**value)
        else:
            raise TypeError("%r is not of type %s or dict" % (value, expected))

    return converter


def converter_list(expected):
    """Convert the given value to a list of objects of type `expected`."""

    def converter(value):
        if isinstance(value, list):
            if len(value) == 0:
                return value
            else:
                new_list = []
                for item in value:
                    if isinstance(item, expected):
                        new_list.append(item)
                    elif isinstance(item, dict):
                        new_list.append(expected(**item))
                    else:
                        raise TypeError(
                            "Item %r is not of type %s or dict"
                            % (item, expected)
                        )
                return new_list
        else:
            raise TypeError("%r is not of type list" % value)

    return converter


class Capabilities:
    """Capabilities that a pod supports."""

    # Supports the ability for machines to be composable. Driver must
    # implement the `compose` and `decompose` methods when set.
    COMPOSABLE = "composable"

    # Supports fixed local storage. Block devices are fixed in size locally
    # and its possible to get a disk larger than requested.
    FIXED_LOCAL_STORAGE = "fixed_local_storage"

    # Supports dynamic local storage. Block devices are dynamically created,
    # attached locally and will always be the exact requested size.
    DYNAMIC_LOCAL_STORAGE = "dynamic_local_storage"

    # Supports built-in iscsi storage. Remote block devices can be created of
    # exact size with this pod connected storage systems.
    ISCSI_STORAGE = "iscsi_storage"

    # Ability to overcommit the cores and memory of the pod. Mainly used
    # for virtual pod.
    OVER_COMMIT = "over_commit"

    # Pod has a multiple storage pools, that can be used when composing
    # a new machine.
    STORAGE_POOLS = "storage_pools"


class BlockDeviceType:
    """Different types of block devices."""

    # Block device is connected physically to the discovered machine.
    PHYSICAL = "physical"

    # Block device is connected to the discovered device over iSCSI.
    ISCSI = "iscsi"


class InterfaceAttachType:
    """Different interface attachment types."""

    # Interface attached to a network predefined in the hypervisor.
    # (This is the default if no constraints are specified; MAAS will look for
    # a 'maas' network, and then fall back to a 'default' network.)
    NETWORK = "network"

    # Interface attached to a bridge interface on the hypervisor.
    BRIDGE = "bridge"

    # Interface attached via a non-bridge interface using the macvlan driver.
    MACVLAN = "macvlan"

    # Interface attached via an SR-IOV capable device.
    SRIOV = "sriov"


class AttrHelperMixin:
    """Mixin to add the `fromdict` and `asdict` to the classes."""

    @classmethod
    def fromdict(cls, data):
        """Convert from a dictionary."""
        return cls(**data)

    def asdict(self):
        """Convert to a dictionary."""
        return attr.asdict(self)


@attr.s
class DiscoveredMachineInterface(AttrHelperMixin):
    """Discovered machine interface."""

    mac_address = attr.ib(converter=str)
    vid = attr.ib(converter=int, default=-1)
    tags = attr.ib(converter=converter_list(str), default=attr.Factory(list))
    boot = attr.ib(converter=bool, default=False)
    attach_type = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )
    attach_name = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )


@attr.s
class DiscoveredMachineBlockDevice(AttrHelperMixin):
    """Discovered machine block device."""

    model = attr.ib(converter=converter_obj(str, optional=True))
    serial = attr.ib(converter=converter_obj(str, optional=True))
    size = attr.ib(converter=int)
    block_size = attr.ib(converter=int, default=512)
    tags = attr.ib(converter=converter_list(str), default=attr.Factory(list))
    id_path = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )
    type = attr.ib(converter=str, default=BlockDeviceType.PHYSICAL)

    # Optional id of the storage pool this block device exists on. Only
    # used when the Pod supports STORAGE_POOLS.
    storage_pool = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )

    # Used when `type` is set to `BlockDeviceType.ISCSI`. The pod driver must
    # define an `iscsi_target` or it will not create the device for the
    # discovered machine.
    iscsi_target = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )


@attr.s
class DiscoveredMachine(AttrHelperMixin):
    """Discovered machine."""

    architecture = attr.ib(converter=str)
    cores = attr.ib(converter=int)
    cpu_speed = attr.ib(converter=int)
    memory = attr.ib(converter=int)
    interfaces = attr.ib(converter=converter_list(DiscoveredMachineInterface))
    block_devices = attr.ib(
        converter=converter_list(DiscoveredMachineBlockDevice)
    )
    power_state = attr.ib(converter=str, default="unknown")
    power_parameters = attr.ib(
        converter=converter_obj(dict), default=attr.Factory(dict)
    )
    tags = attr.ib(converter=converter_list(str), default=attr.Factory(list))
    hostname = attr.ib(converter=str, default=None)
    pinned_cores = attr.ib(
        converter=converter_list(int), default=attr.Factory(list)
    )
    hugepages_backed = attr.ib(converter=bool, default=False)


@attr.s
class DiscoveredPodStoragePool(AttrHelperMixin):
    """Discovered pod storage pool.

    Provide information on the storage pool.
    """

    id = attr.ib(converter=str)
    name = attr.ib(converter=str)
    path = attr.ib(converter=str)
    type = attr.ib(converter=str)
    storage = attr.ib(converter=int)


@attr.s
class DiscoveredPodHints(AttrHelperMixin):
    """Discovered pod hints.

    Hints provide helpful information to a user trying to compose a machine.
    Limiting the maximum cores allow request on a per machine basis.
    """

    cores = attr.ib(converter=int, default=-1)
    cpu_speed = attr.ib(converter=int, default=-1)
    memory = attr.ib(converter=int, default=-1)
    local_storage = attr.ib(converter=int, default=-1)
    local_disks = attr.ib(converter=int, default=-1)
    iscsi_storage = attr.ib(converter=int, default=-1)


@attr.s
class DiscoveredPod(AttrHelperMixin):
    """Discovered pod information."""

    architectures = attr.ib(converter=converter_list(str))
    name = attr.ib(converter=converter_obj(str, optional=True), default=None)
    cores = attr.ib(converter=int, default=-1)
    cpu_speed = attr.ib(converter=int, default=-1)
    memory = attr.ib(converter=int, default=-1)
    local_storage = attr.ib(converter=int, default=-1)
    hints = attr.ib(
        converter=converter_obj(DiscoveredPodHints),
        default=DiscoveredPodHints(),
    )
    local_disks = attr.ib(converter=int, default=-1)
    iscsi_storage = attr.ib(converter=int, default=-1)
    # XXX - This should be the hardware UUID but LXD doesn't provide it.
    mac_addresses = attr.ib(
        converter=converter_list(str), default=attr.Factory(list)
    )
    capabilities = attr.ib(
        converter=converter_list(str),
        default=attr.Factory(lambda: [Capabilities.FIXED_LOCAL_STORAGE]),
    )
    machines = attr.ib(
        converter=converter_list(DiscoveredMachine), default=attr.Factory(list)
    )
    tags = attr.ib(converter=converter_list(str), default=attr.Factory(list))
    storage_pools = attr.ib(
        converter=converter_list(DiscoveredPodStoragePool),
        default=attr.Factory(list),
    )


@attr.s
class RequestedMachineBlockDevice(AttrHelperMixin):
    """Requested machine block device information."""

    size = attr.ib(converter=int)
    tags = attr.ib(converter=converter_list(str), default=attr.Factory(list))


@attr.s
class RequestedMachineInterface(AttrHelperMixin):
    """Requested machine interface information."""

    ifname = attr.ib(converter=converter_obj(str, optional=True), default=None)
    attach_name = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )
    attach_type = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )
    attach_options = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )
    attach_vlan = attr.ib(
        converter=converter_obj(int, optional=True), default=None
    )
    requested_ips = attr.ib(
        converter=converter_list(str), default=attr.Factory(list)
    )
    ip_mode = attr.ib(
        converter=converter_obj(str, optional=True), default=None
    )


@attr.s
class KnownHostInterface(AttrHelperMixin):
    """Known host interface information."""

    ifname = attr.ib(converter=str, default=None)
    attach_type = attr.ib(converter=str, default=None)
    attach_name = attr.ib(converter=str, default=None)
    attach_vlan = attr.ib(
        converter=converter_obj(int, optional=True), default=None
    )
    dhcp_enabled = attr.ib(converter=bool, default=False)


@attr.s
class RequestedMachine(AttrHelperMixin):
    """Requested machine information."""

    hostname = attr.ib(converter=str)
    architecture = attr.ib(converter=str)
    cores = attr.ib(converter=int)
    memory = attr.ib(converter=int)
    block_devices = attr.ib(
        converter=converter_list(RequestedMachineBlockDevice)
    )
    interfaces = attr.ib(converter=converter_list(RequestedMachineInterface))

    # Optional fields.
    cpu_speed = attr.ib(
        converter=converter_obj(int, optional=True), default=None
    )
    known_host_interfaces = attr.ib(
        converter=converter_list(KnownHostInterface),
        default=attr.Factory(list),
    )

    @classmethod
    def fromdict(cls, data):
        """Convert from a dictionary."""
        return cls(**data)

    def asdict(self):
        """Convert to a dictionary."""
        return attr.asdict(self)


class PodDriverBase(PowerDriverBase):
    """Base driver for a pod driver."""

    @abstractmethod
    def discover(self, pod_id, context):
        """Discover the pod resources.

        :param context: Pod settings.
        :param pod_id: Pod id.
        :returns: `Deferred` returning `DiscoveredPod`.
        :rtype: `twisted.internet.defer.Deferred`
        """

    @abstractmethod
    def compose(self, pod_id, context, request):
        """Compose a node from parameters in context.

        :param pod_id: Pod id.
        :param context: Pod settings.
        :param request: Requested machine.
        :type request: `RequestedMachine`.
        :returns: Tuple with (`DiscoveredMachine`, `DiscoveredPodHints`).
        """

    @abstractmethod
    def decompose(self, pod_id, context):
        """Decompose a node.

        :param pod_id: Pod id.
        :param context:  Pod settings.
        """

    def get_commissioning_data(self, pod_id, context):
        """Retreive commissioning data from the Pod host.

        :param pod_id: Pod id.
        :param context: Pod settings.
        :returns: Dictionary mapping builtin commissioning script names with
        data to be sent to the metadata server.
        """
        raise NotImplementedError()

    def get_schema(self, detect_missing_packages=True):
        """Returns the JSON schema for the driver.

        Calculates the missing packages on each invoke.
        """
        schema = super().get_schema(
            detect_missing_packages=detect_missing_packages
        )
        schema["driver_type"] = "pod"
        return schema


def get_error_message(err):
    """Returns the proper error message based on error."""
    if isinstance(err, PodAuthError):
        return "Could not authenticate to pod: %s" % err
    elif isinstance(err, PodConnError):
        return "Could not contact pod: %s" % err
    elif isinstance(err, PodActionError):
        return "Failed to complete pod action: %s" % err
    else:
        return "Failed talking to pod: %s" % err


class PodDriver(PowerDriver, PodDriverBase):
    """Default pod driver."""

    chassis = True  # Pods are always a chassis
