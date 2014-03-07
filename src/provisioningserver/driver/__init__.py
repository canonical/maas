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

    def __init__(self, name, pxealiases=None):
        """Represents an architecture in the driver context.

        :param name: The architecture name as used in MAAS.
            arch/subarch or just arch.
        :param pxealiases: The optional list of names used if the
            hardware uses a different name when requesting its bootloader.
        """
        self.name = name
        self.pxealiases = pxealiases

    def map_to_maas_name(self, alias):
        if alias in self.pxealiases:
            return self.name
        return alias


class BootResource:
    """Abstraction of ephemerals and pxe resources required for a hardware
    driver.

    This resource is responsible for importing and reporting on
    what is potentially available in relation to a cluster controller.
    """

    __metaclass__ = ABCMeta

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


class ArchitectureRegistry:
    """Store all known architectures in here."""

    architectures = []

    @classmethod
    def register_architecture(cls, architecture):
        cls.architectures.append(architecture)


builtin_architectures = [
    Architecture("i386"),
    Architecture("amd64"),
    Architecture("armhf", ["arm"]),
]
for arch in builtin_architectures:
    ArchitectureRegistry.register_architecture(arch)


# TODO:
#  * registry for power types
#  * registry for boot resources
#  * registry for actual drivers
#  * hook RPC calls to registry data
