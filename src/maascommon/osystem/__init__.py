# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Osystem Drivers."""

from abc import ABCMeta, abstractmethod
from collections import namedtuple

from maascommon.utils.registry import Registry


class NoSuchOperatingSystem(Exception):
    """The specified OS was not found."""


class BOOT_IMAGE_PURPOSE:
    """The vocabulary of a `BootImage`'s purpose."""

    # Usable for commissioning
    COMMISSIONING = "commissioning"
    # Usable for install
    INSTALL = "install"
    # Usable for fast-path install
    XINSTALL = "xinstall"
    # Usable for diskless boot
    DISKLESS = "diskless"
    # Bootloader for enlistment, commissioning, and deployment
    BOOTLOADER = "bootloader"


# A cluster-side representation of a Node, relevant to the osystem code,
# with only minimal fields.
Node = namedtuple("Node", ("system_id", "hostname"))


# A cluster-side representation of a Token, relevant to the osystem code,
# with only minimal fields.
Token = namedtuple("Token", ("consumer_key", "token_key", "token_secret"))


class OperatingSystem(metaclass=ABCMeta):
    """Skeleton for an operating system."""

    # Name of the operating system
    name: str
    # Title of the operating system
    title: str

    @property
    def default_fname(self) -> str | None:
        """Default image filename"""
        return None

    @abstractmethod
    def get_default_release(self) -> str:
        """Return the default release to use when none is specified.

        :return: default release to use
        """

    @abstractmethod
    def get_release_title(self, release) -> str | None:
        """Return the given release's title.

        :type release: unicode
        :return: unicode
        """

    @abstractmethod
    def get_boot_image_purposes(self) -> list[str]:
        """Return a boot image's supported purposes.

        :return: list of supported purposes
        """

    def is_release_supported(self, release) -> bool:
        """Return True when the release is supported, False otherwise."""
        # If the osystem matches assume all releases are supported.
        return True

    def format_release_choices(self, releases):
        """Format the release choices that are presented to the user.

        :param releases: list of installed boot image releases
        :return: Return Django "choices" list
        """
        choices = []
        releases = sorted(releases, reverse=True)
        for release in releases:
            title = self.get_release_title(release)
            if title is not None:
                choices.append((release, title))
        return choices

    def get_supported_releases(self) -> set[str]:
        """Return operating system's supported releases as a set.

        :return: set of supported releases
        """
        return set()

    def get_supported_commissioning_releases(self):
        """List operating system's supported commissioning releases.

        Typically this will only return something for Ubuntu, because
        that is the only operating system on which we commission.

        :return: list of releases.
        """
        return []

    def get_default_commissioning_release(self) -> str | None:
        """Return operating system's default commissioning release.

        Typically this will only return something for Ubuntu, because
        that is the only operating system on which we commission.

        :return: a release name, or ``None``.
        """
        return None

    def requires_license_key(self, release) -> bool:
        """Return whether the given release requires a license key.

        :param release: Release
        :return: True if requires license key, false otherwise.
        """
        return False

    def validate_license_key(self, release: str, key: str) -> bool:
        """Validate a license key for a release.

        This is only called if the release requires a license key.

        :param release: Release
        :param key: License key
        :return: True if valid, False otherwise
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
        :return: Preseed data for node.
        :raise:
            NotImplementedError: doesn't implement a custom preseed
        """
        raise NotImplementedError()

    def _get_image_filetypes(
        self,
        squashfs=False,
        tgz=False,
        dd=False,
    ) -> dict[str, str]:
        assert squashfs or tgz or dd, "One type must be selected"
        filetypes: dict[str, str] = {}
        if squashfs:
            filetypes.update({"squashfs": "squashfs"})
        if tgz:
            # Initially uploaded images were named root-$ext, but were
            # renamed to root.$ext to support ephemeral deploys. We need to
            # check both old and new formats, since images from the
            # images.maas.io still uses the old format.
            filetypes.update(
                {"root-tgz": "tgz", "root-txz": "txz", "root-tbz": "tbz"}
            )
            filetypes.update(
                {"root.tgz": "tgz", "root.txz": "txz", "root.tbz": "tbz"}
            )
        if dd:
            filetypes.update(
                {
                    # root-dd maps to dd-tgz for backwards compatibility.
                    "root-dd": "dd-tgz",
                    "root-dd.tar": "dd-tar",
                    "root-dd.raw": "dd-raw",
                    "root-dd.bz2": "dd-bz2",
                    "root-dd.gz": "dd-gz",
                    "root-dd.xz": "dd-xz",
                    "root-dd.tar.bz2": "dd-tbz",
                    "root-dd.tar.xz": "dd-txz",
                }
            )
        return filetypes

    def get_image_filetypes(self) -> dict[str, str]:
        return self._get_image_filetypes(tgz=True)


class OperatingSystemRegistry(Registry):
    """Registry for operating system classes."""


from maascommon.osystem.bootloader import BootLoaderOS  # noqa:E402 isort:skip
from maascommon.osystem.centos import CentOS  # noqa:E402 isort:skip
from maascommon.osystem.custom import CustomOS  # noqa:E402 isort:skip
from maascommon.osystem.esxi import ESXi  # noqa:E402 isort:skip
from maascommon.osystem.ol import OL  # noqa:E402 isort:skip
from maascommon.osystem.rhel import RHELOS  # noqa:E402 isort:skip
from maascommon.osystem.suse import SUSEOS  # noqa:E402 isort:skip
from maascommon.osystem.ubuntu import UbuntuOS  # noqa:E402 isort:skip
from maascommon.osystem.ubuntucore import UbuntuCoreOS  # noqa:E402 isort:skip
from maascommon.osystem.windows import WindowsOS  # noqa:E402 isort:skip


def validate_license_key(osystem: str, release: str, key: str) -> bool:
    """Validate a license key.

    :raises NoSuchOperatingSystem: If ``osystem`` is not found.
    """
    try:
        osystem = OperatingSystemRegistry[osystem]
    except KeyError:
        raise NoSuchOperatingSystem(osystem)  # noqa: B904
    else:
        return osystem.validate_license_key(release, key)  # type: ignore


builtin_osystems = [
    UbuntuOS(),
    UbuntuCoreOS(),
    BootLoaderOS(),
    CentOS(),
    RHELOS(),
    CustomOS(),
    WindowsOS(),
    SUSEOS(),
    ESXi(),
    OL(),
]
for osystem in builtin_osystems:
    OperatingSystemRegistry.register_item(osystem.name, osystem)
