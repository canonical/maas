# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Osystem Drivers."""


from abc import ABCMeta, abstractmethod, abstractproperty
from collections import namedtuple
import os

from provisioningserver.config import ClusterConfiguration
from provisioningserver.utils.registry import Registry


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


def list_boot_images_for(osystem):
    """List all boot images for the given osystem."""
    # Circular import
    from provisioningserver.rpc.boot_images import list_boot_images

    return [
        image
        for image in list_boot_images()
        if image["osystem"] == osystem.name
    ]


class OperatingSystem(metaclass=ABCMeta):
    """Skeleton for an operating system."""

    @abstractproperty
    def name(self):
        """Name of the operating system."""

    @abstractproperty
    def title(self):
        """Title of the operating system."""

    @abstractmethod
    def get_default_release(self):
        """Return the default release to use when none is specified.

        :return: default release to use
        """

    @abstractmethod
    def get_release_title(self, release):
        """Return the given release's title.

        :type release: unicode
        :return: unicode
        """

    @abstractmethod
    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Return a boot image's supported purposes.

        :param arch: Architecture of boot image.
        :param subarch: Sub-architecture of boot image.
        :param release: Release of boot image.
        :param label: Label of boot image.
        :return: list of supported purposes
        """

    def is_release_supported(self, release):
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

    def gen_supported_releases(self):
        """List operating system's supported releases.

        This is based off the boot images that the cluster currently has
        for this operating system.
        """
        for image in list_boot_images_for(self):
            release = image["release"]
            if self.is_release_supported(release):
                yield release

    def get_supported_releases(self):
        """Return operating system's supported releases as a set.

        This is based off the boot images that the cluster currently has
        for this operating system.

        :return: set of supported releases
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
        :return: True if requires license key, false otherwise.
        """
        return False

    def validate_license_key(self, release, key):
        """Validate a license key for a release.

        This is only called if the release requires a license key.

        :param release: Release
        :param key: License key
        :return: True if valid, false otherwise
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

    def _find_image(
        self,
        arch,
        subarch,
        release,
        label,
        squashfs=False,
        tgz=False,
        dd=False,
        default_fname=None,
    ):
        filetypes = {}
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

        with ClusterConfiguration.open() as config:
            base_path = os.path.join(
                config.tftp_root, self.name, arch, subarch, release, label
            )

        try:
            for fname in os.listdir(base_path):
                if fname in filetypes.keys():
                    return fname, filetypes[fname]
        except FileNotFoundError:
            # In case the path does not exist
            pass

        assert squashfs or tgz or dd, "One type must be selected"
        # If none is found return the default for messaging.
        if default_fname and default_fname in filetypes:
            return default_fname, filetypes[default_fname]
        else:
            return list(filetypes.items())[0]

    def get_xinstall_parameters(self, arch, subarch, release, label):
        """Return the xinstall image name and type for this operating system.

        :param arch: Architecture of boot image.
        :param subarch: Sub-architecture of boot image.
        :param release: Release of boot image.
        :param label: Label of boot image.
        :return: tuple with name of root image and image type
        """
        return self._find_image(arch, subarch, release, label, tgz=True)


class OperatingSystemRegistry(Registry):
    """Registry for operating system classes."""


from provisioningserver.drivers.osystem.bootloader import (  # noqa:E402 isort:skip
    BootLoaderOS,
)
from provisioningserver.drivers.osystem.centos import (  # noqa:E402 isort:skip
    CentOS,
)
from provisioningserver.drivers.osystem.custom import (  # noqa:E402 isort:skip
    CustomOS,
)
from provisioningserver.drivers.osystem.esxi import (  # noqa:E402 isort:skip
    ESXi,
)
from provisioningserver.drivers.osystem.ol import (  # noqa:E402 isort:skip
    OL,
)
from provisioningserver.drivers.osystem.rhel import (  # noqa:E402 isort:skip
    RHELOS,
)
from provisioningserver.drivers.osystem.suse import (  # noqa:E402 isort:skip
    SUSEOS,
)
from provisioningserver.drivers.osystem.ubuntu import (  # noqa:E402 isort:skip
    UbuntuOS,
)
from provisioningserver.drivers.osystem.ubuntucore import (  # noqa:E402 isort:skip
    UbuntuCoreOS,
)
from provisioningserver.drivers.osystem.windows import (  # noqa:E402 isort:skip
    WindowsOS,
)

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
