#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


from enum import IntEnum, StrEnum


class BootResourceType(IntEnum):
    """Possible types for `BootResource`."""

    SYNCED = 0  # downloaded from BootSources
    # index 1 was GENERATED, now unused
    UPLOADED = 2  # uploaded by user


# A means of gets a human-readble string from boot resource type.
BOOT_RESOURCE_TYPE_DICT = {
    BootResourceType.SYNCED: "Synced",
    BootResourceType.UPLOADED: "Uploaded",
}


class BootResourceStrType(StrEnum):
    """Possible selections for the type of `BootResource`."""

    SYNCED = "synced"
    UPLOADED = "uploaded"


class BootResourceFileType(StrEnum):
    """The vocabulary of possible file types for `BootResource`."""

    # Tarball of root image.
    ROOT_TGZ = "root-tgz"
    ROOT_TBZ = "root-tbz"
    ROOT_TXZ = "root-txz"

    # Tarball of dd image.
    ROOT_DD = "root-dd"
    ROOT_DDTAR = "root-dd.tar"

    # Raw dd image
    ROOT_DDRAW = "root-dd.raw"

    # Compressed dd image types
    ROOT_DDBZ2 = "root-dd.bz2"
    ROOT_DDGZ = "root-dd.gz"
    ROOT_DDXZ = "root-dd.xz"

    # Compressed tarballs of dd images
    ROOT_DDTBZ = "root-dd.tar.bz2"
    ROOT_DDTXZ = "root-dd.tar.xz"
    # For backwards compatibility, DDTGZ files are named root-dd
    ROOT_DDTGZ = "root-dd"

    # Following are not allowed on user upload. Only used for syncing
    # from another simplestreams source. (Most likely images.maas.io)

    # Root Image (gets converted to root-image root-tgz, on the rack)
    ROOT_IMAGE = "root-image.gz"

    # Root image in SquashFS form, does not need to be converted
    SQUASHFS_IMAGE = "squashfs"

    # Boot Kernel
    BOOT_KERNEL = "boot-kernel"

    # Boot Initrd
    BOOT_INITRD = "boot-initrd"

    # Boot DTB
    BOOT_DTB = "boot-dtb"

    # tar.xz of files which need to be extracted so the files are usable
    # by MAAS
    ARCHIVE_TAR_XZ = "archive.tar.xz"
