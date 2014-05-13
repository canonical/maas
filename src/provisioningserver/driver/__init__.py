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
    "OperatingSystem",
    "OperatingSystemRegistry",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )

from provisioningserver.power_schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.utils.registry import Registry


class BOOT_IMAGE_PURPOSE:
    """The vocabulary of a `BootImage`'s purpose."""
    #: Usable for commissioning
    COMMISSIONING = 'commissioning'
    #: Usable for install
    INSTALL = 'install'
    #: Usable for fast-path install
    XINSTALL = 'xinstall'


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
        if pxealiases is None:
            pxealiases = ()
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
            e.g. "release=trusty label=beta-2 arch=amd64"
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
                "label": "beta-2",
                "size": 12344556,
            }
            ,
        ]
        """


class OperatingSystem:
    """Skeleton for an operating system."""

    __metaclass__ = ABCMeta

    @abstractproperty
    def name(self):
        """Name of the operating system."""

    @abstractproperty
    def title(self):
        """Title of the operating system."""

    @abstractmethod
    def get_supported_releases(self):
        """Gets list of supported releases for Ubuntu.

        :returns: list of supported releases
        """

    @abstractmethod
    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit.

        :returns: default release to use
        """

    @abstractmethod
    def format_release_choices(self, releases):
        """Formats the release choices that are presented to the user.

        :param releases: list of installed boot image releases
        :returns: Return Django "choices" list
        """

    @abstractmethod
    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Returns the supported purposes of a boot image.

        :param arch: Architecture of boot image.
        :param subarch: Sub-architecture of boot image.
        :param release: Release of boot image.
        :param label: Label of boot image.
        :returns: list of supported purposes
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
    """Registry for architecture classes."""

    @classmethod
    def get_by_pxealias(cls, alias):
        for _, arch in cls:
            if alias in arch.pxealiases:
                return arch
        return None


class BootResourceRegistry(Registry):
    """Registry for boot resource classes."""


class OperatingSystemRegistry(Registry):
    """Registry for operating system classes."""


class PowerTypeRegistry(Registry):
    """Registry for power type classes."""


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
    ArchitectureRegistry.register_item(arch.name, arch)


builtin_power_types = JSON_POWER_TYPE_PARAMETERS
for power_type in builtin_power_types:
    PowerTypeRegistry.register_item(power_type['name'], power_type)


from provisioningserver.driver.os_ubuntu import UbuntuOS
builtin_osystems = [
    UbuntuOS(),
    ]
for osystem in builtin_osystems:
    OperatingSystemRegistry.register_item(osystem.name, osystem)
