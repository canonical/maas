# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Osystem Drivers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "OperatingSystem",
    "OperatingSystemRegistry",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )

from provisioningserver.utils.registry import Registry


class BOOT_IMAGE_PURPOSE:
    """The vocabulary of a `BootImage`'s purpose."""
    #: Usable for commissioning
    COMMISSIONING = 'commissioning'
    #: Usable for install
    INSTALL = 'install'
    #: Usable for fast-path install
    XINSTALL = 'xinstall'


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

    def requires_license_key(self, release):
        """Returns whether the given release requires a licese key.

        :param release: Release
        :returns: True if requires license key, false otherwise.
        """
        return False

    def validate_license_key(self, release, key):
        """Validates a license key for a release. This is only called if
        the release requires a license key.

        :param release: Release
        :param key: License key
        :returns: True if valid, false otherwise
        """
        raise NotImplementedError()

    def compose_preseed(self, preseed_type, node, token, metadata_url):
        """Composes the preseed for the given node.

        :param preseed_type: Preseed type to compose.
        :param node: Node preseed needs generating.
        :param token: OAuth token for url.
        :param metadata_url: Metdata url for node.
        :returns: Preseed for node.
        :raise:
            NotImplementedError: doesn't implement a custom preseed
        """
        raise NotImplementedError()


class OperatingSystemRegistry(Registry):
    """Registry for operating system classes."""


from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.drivers.osystem.centos import CentOS
builtin_osystems = [
    UbuntuOS(),
    CentOS(),
    ]
for osystem in builtin_osystems:
    OperatingSystemRegistry.register_item(osystem.name, osystem)
