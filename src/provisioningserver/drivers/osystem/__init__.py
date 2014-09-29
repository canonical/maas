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
    "Node",
    "OperatingSystem",
    "OperatingSystemRegistry",
    "Token",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )
from collections import namedtuple

from provisioningserver.utils.registry import Registry


class BOOT_IMAGE_PURPOSE:
    """The vocabulary of a `BootImage`'s purpose."""
    #: Usable for commissioning
    COMMISSIONING = 'commissioning'
    #: Usable for install
    INSTALL = 'install'
    #: Usable for fast-path install
    XINSTALL = 'xinstall'
    #: Usable for diskless boot
    DISKLESS = 'diskless'


# A cluster-side representation of a Node, relevant to the osystem code,
# with only minimal fields.
Node = namedtuple("Node", ("system_id", "hostname"))


# A cluster-side representation of a Token, relevant to the osystem code,
# with only minimal fields.
Token = namedtuple("Token", ("consumer_key", "token_key", "token_secret"))


def list_boot_images_for(osystem):
    """List all boot images for the given osystem."""
    # Circular import
    from provisioningserver.rpc.boot_images import list_boot_images
    return [
        image
        for image in list_boot_images()
        if image['osystem'] == osystem.name
        ]


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
    def is_release_supported(self, release):
        """Return True when the release is supported, False otherwise."""

    @abstractmethod
    def get_default_release(self):
        """Return the default release to use when none is specified.

        :returns: default release to use
        """

    @abstractmethod
    def get_release_title(self, release):
        """Return the given release's title.

        :type release: unicode
        :returns: unicode
        """

    @abstractmethod
    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Return a boot image's supported purposes.

        :param arch: Architecture of boot image.
        :param subarch: Sub-architecture of boot image.
        :param release: Release of boot image.
        :param label: Label of boot image.
        :returns: list of supported purposes
        """

    def format_release_choices(self, releases):
        """Format the release choices that are presented to the user.

        :param releases: list of installed boot image releases
        :returns: Return Django "choices" list
        """
        choices = []
        releases = sorted(releases, reverse=True)
        for release in releases:
            title = self.get_release_title(release)
            if title is not None:
                choices.append((release, title))
        return choices

    def gen_supported_releases(self):
        """List operating system's supported releases.

        This is based off the boot images that the cluster currently has
        for this operating system.
        """
        for image in list_boot_images_for(self):
            release = image['release']
            if self.is_release_supported(release):
                yield release

    def get_supported_releases(self):
        """Return operating system's supported releases as a set.

        This is based off the boot images that the cluster currently has
        for this operating system.

        :returns: set of supported releases
        """
        return set(self.gen_supported_releases())

    def get_supported_commissioning_releases(self):
        """List operating system's supported commissioning releases.

        Typically this will only return something for Ubuntu, because
        that is the only operating system on which we commission.

        :return: list of releases.
        """
        return []

    def get_default_commissioning_release(self):
        """Return operating system's default commissioning release.

        Typically this will only return something for Ubuntu, because
        that is the only operating system on which we commission.

        :return: a release name, or ``None``.
        """
        return None

    def requires_license_key(self, release):
        """Return whether the given release requires a license key.

        :param release: Release
        :returns: True if requires license key, false otherwise.
        """
        return False

    def validate_license_key(self, release, key):
        """Validate a license key for a release.

        This is only called if the release requires a license key.

        :param release: Release
        :param key: License key
        :returns: True if valid, false otherwise
        """
        raise NotImplementedError()

    def compose_preseed(self, preseed_type, node, token, metadata_url):
        """Compose preseed for the given node.

        :param preseed_type: Preseed type to compose.
        :param node: Node preseed needs generating for.
        :type node: :py:class:`Node`
        :param token: OAuth token for URL.
        :type token: :py:class:`Token`
        :param metadata_url: Metdata URL for node.
        :returns: Preseed data for node.
        :raise:
            NotImplementedError: doesn't implement a custom preseed
        """
        raise NotImplementedError()

    def get_xinstall_parameters(self, arch, subarch, release, label):
        """Return the xinstall image name and type for this operating system.

        :param arch: Architecture of boot image.
        :param subarch: Sub-architecture of boot image.
        :param release: Release of boot image.
        :param label: Label of boot image.
        :returns: tuple with name of root image and image type
        """
        return "root-tgz", "tgz"


class OperatingSystemRegistry(Registry):
    """Registry for operating system classes."""


from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.drivers.osystem.centos import CentOS
from provisioningserver.drivers.osystem.custom import CustomOS
from provisioningserver.drivers.osystem.windows import WindowsOS
from provisioningserver.drivers.osystem.suse import SUSEOS

builtin_osystems = [
    UbuntuOS(),
    CentOS(),
    CustomOS(),
    WindowsOS(),
    SUSEOS(),
    ]
for osystem in builtin_osystems:
    OperatingSystemRegistry.register_item(osystem.name, osystem)
