# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Hardware Drivers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Architecture",
    "ArchitectureRegistry",
    "BootResource",
    "HardwareDriver",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )

from provisioningserver.driver.registry import Registry
from provisioningserver.power_schema import JSON_POWER_TYPE_PARAMETERS


class HardwareDriver:
    """A rough skeleton for a hardware driver.

    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, architecture_driver, power_type):  # release series?
        """Constructor for every hardware driver.
        TODO params.
        """

    @abstractproperty
    def architecture(self):
        """The :class:`ArchitectureDriver` instance for this driver."""

    @abstractproperty
    def power_action(self):
        """The :class:`PowerAction` instance for this driver."""

    @abstractmethod
    def kernel_options(self, purpose):
        """Custom kernel options for kernels booted by this driver."""
        # Used by kernel_opts.py

    @abstractmethod
    def get_ephemeral_name(self, release):
        """Return the ephemeral image name used for iscsi target."""
        # Used by kernel_opts.py


class Architecture:

    def __init__(self, name, description, pxealiases=None,
                 kernel_options=None):
        """Represents an architecture in the driver context.

        :param name: The architecture name as used in MAAS.
            arch/subarch or just arch.
        :param description: The human-readable description for the
            architecture.
        :param pxealiases: The optional list of names used if the
            hardware uses a different name when requesting its bootloader.
        :param kernel_options: The optional list of kernel options for this
            architecture.  Anything supplied here supplements the options
            provided by MAAS core.
        """
        self.name = name
        self.description = description
        self.pxealiases = pxealiases
        self.kernel_options = kernel_options


class BootResource:
    """Abstraction of ephemerals and pxe resources required for a hardware
    driver.

    This resource is responsible for importing and reporting on
    what is potentially available in relation to a cluster controller.
    """

    __metaclass__ = ABCMeta

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def import_resources(self, at_location, filter=None):
        """Import the specified resources.

        :param at_location: URL to a Simplestreams index or a local path
            to a directory containing boot resources.
        :param filter: A simplestreams filter.
            e.g. "release=trusty label=beta2 arch=amd64"
            This is ignored if the location is a local path, all resources
            at the location will be imported.
        TBD: How to provide progress information.
        """

    @abstractmethod
    def describe_resources(self, at_location):
        """Enumerate all the boot resources.

        :param at_location: URL to a Simplestreams index or a local path
            to a directory containing boot resources.

        :return: a list of dictionaries describing the available resources,
            which will need to be imported so the driver can use them.
        [
            {
                "release": "trusty",
                "arch": "amd64",
                "label": "beta2",
                "size": 12344556,
            }
            ,
        ]
        """


class HardwareDiscoverContext:

    __metaclass__ = ABCMeta

    @abstractmethod
    def startDiscovery(self):
        """TBD"""

    @abstractmethod
    def stopDiscovery(self):
        """TBD"""


class ArchitectureRegistry(Registry):
    registry_name = "architecture"

    @classmethod
    def get_by_pxealias(cls, alias):
        for arch in cls.get_items().values():
            if alias in arch.pxealiases:
                return arch
        return None


class BootResourceRegistry(Registry):
    registry_name = "bootresource"


class PowerTypeRegistry(Registry):
    registry_name = "power_type"


builtin_architectures = [
    Architecture(name="i386/generic", description="i386"),
    Architecture(name="amd64/generic", description="amd64"),
    Architecture(
        name="armhf/highbank", description="armhf/highbank",
        pxealiases=["arm"], kernel_options=["console=ttyAMA0"]),
    Architecture(
        name="armhf/generic", description="armhf/generic",
        pxealiases=["arm"], kernel_options=["console=ttyAMA0"]),
]
for arch in builtin_architectures:
    ArchitectureRegistry.register_item(arch, arch.name)


builtin_power_types = JSON_POWER_TYPE_PARAMETERS
for power_type in builtin_power_types:
    PowerTypeRegistry.register_item(power_type, power_type['name'])
