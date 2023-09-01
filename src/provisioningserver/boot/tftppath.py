# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Construct TFTP paths for boot files."""


import errno
from itertools import chain
import os.path

from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystemRegistry,
)
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
)
from provisioningserver.import_images.helpers import ImageSpec
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("tftp")


def compose_image_path(osystem, arch, subarch, release, label):
    """Compose the TFTP path for a PXE kernel/initrd directory.

    The path returned is relative to the TFTP root, as it would be
    identified by clients on the network.

    :param osystem: Operating system.
    :param arch: Main machine architecture.
    :param subarch: Sub-architecture, or "generic" if there is none.
    :param release: Operating system release, e.g. "precise".
    :param label: Release label, e.g. "release" or "alpha-2".
    :return: Path for the corresponding image directory (containing a
        kernel and initrd) as exposed over TFTP.
    """
    # This is a TFTP path, not a local filesystem path, so hard-code the slash.
    return "/".join([osystem, arch, subarch, release, label])


def is_visible_subdir(directory, subdir):
    """Is `subdir` a non-hidden sub-directory of `directory`?"""
    if subdir.startswith("."):
        return False
    else:
        return os.path.isdir(os.path.join(directory, subdir))


def list_subdirs(directory):
    """Return a list of non-hidden directories in `directory`."""
    return [
        subdir
        for subdir in os.listdir(directory)
        if is_visible_subdir(directory, subdir)
    ]


def extend_path(directory, path):
    """Dig one directory level deeper on `os.path.join(directory, *path)`.

    If `path` is a list of consecutive path elements drilling down from
    `directory`, return a list of sub-directory paths leading one step
    further down.

    :param directory: Base directory that `path` is relative to.
    :param path: A path to a subdirectory of `directory`, represented as
        a list of path elements relative to `directory`.
    :return: A list of paths that go one sub-directory level further
        down from `path`.
    """
    return [
        path + [subdir]
        for subdir in list_subdirs(os.path.join(directory, *path))
    ]


def drill_down(directory, paths):
    """Find the extensions of `paths` one level deeper into the filesystem.

    :param directory: Base directory that each path in `paths` is relative to.
    :param paths: A list of "path lists."  Each path list is a list of
        path elements drilling down into the filesystem from `directory`.
    :return: A list of paths, each of which drills one level deeper down into
        the filesystem hierarchy than the originals in `paths`.
    """
    return list(
        chain.from_iterable(extend_path(directory, path) for path in paths)
    )


def extract_metadata(metadata, params):
    """Examine the maas.meta file for any required metadata.

    :param metadata: contents of the maas.meta file
    :param params: A dict of path components for the image
        (architecture, subarchitecture, kflavor, release and label).
    :return: a dict of name/value metadata pairs.  Currently, only
        "subarches" is extracted.
    """
    mapping = BootImageMapping.load_json(metadata)
    subarch = params["subarchitecture"]
    split_subarch = subarch.split("-")
    if len(split_subarch) > 2:
        kflavor = split_subarch[2]
    else:
        kflavor = "generic"

    image = ImageSpec(
        os=params["osystem"],
        arch=params["architecture"],
        subarch=subarch,
        kflavor=kflavor,
        release=params["release"],
        label=params["label"],
    )
    try:
        # On upgrade from 1.5 to 1.6, the subarches does not exist in the
        # maas.meta file . Without this catch boot images will fail to
        # report until the boot images are imported again.
        subarches = mapping.mapping[image]["subarches"]
    except KeyError:
        return {}

    return dict(supported_subarches=subarches)


def extract_image_params(path, maas_meta):
    """Represent a list of TFTP path elements as a list of boot-image dicts.

    :param path: Tuple or list that consists of a full [osystem, architecture,
        subarchitecture, release] that identify a kind of boot for which we
        may need an image.
    :param maas_meta: Contents of the maas.meta file.  This may be an
        empty string.

    :return: A list of dicts, each of which may also include additional
        items of meta-data that are not elements in the path, such as
        "subarches".
    """
    if path[0] == "bootloader":
        osystem, release, arch = path
        subarch = "generic"
        label = "*"
    else:
        osystem, arch, subarch, release, label = path
    osystem_obj = OperatingSystemRegistry.get_item(osystem, default=None)
    if osystem_obj is None:
        return []

    purposes = osystem_obj.get_boot_image_purposes(
        arch, subarch, release, label
    )

    # Expand the path into a list of dicts, one for each boot purpose.
    params = []
    for purpose in purposes:
        image = dict(
            osystem=osystem,
            architecture=arch,
            subarchitecture=subarch,
            release=release,
            label=label,
            purpose=purpose,
        )
        if purpose == BOOT_IMAGE_PURPOSE.XINSTALL:
            xinstall_path, xinstall_type = osystem_obj.get_xinstall_parameters(
                arch, subarch, release, label
            )
            image["xinstall_path"] = xinstall_path
            image["xinstall_type"] = xinstall_type
        else:
            image["xinstall_path"] = ""
            image["xinstall_type"] = ""
        params.append(image)

    # Merge in the meta-data.
    for image_dict in params:
        metadata = extract_metadata(maas_meta, image_dict)
        image_dict.update(metadata)

    return params


def maas_meta_file_path(tftproot):
    """Return a string containing the full path to maas.meta."""
    return os.path.join(tftproot, "maas.meta")


def maas_meta_last_modified(tftproot):
    """Return time of last modification of maas.meta.

    The time is the same as returned from getmtime() (seconds since epoch),
    or None if the file doesn't exist.

    :param tftproot: The TFTP root path.
    """
    meta_file = maas_meta_file_path(tftproot)
    try:
        return os.path.getmtime(meta_file)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return None
        raise


def list_boot_images(tftproot):
    """List the available boot images.

    :param tftproot: TFTP root directory.
    :return: A list of dicts, describing boot images as consumed by the
        `report_boot_images` API call.
    """
    # The sub-directories directly under tftproot, if they contain
    # images, represent operating systems.
    try:
        potential_osystems = list_subdirs(tftproot)
    except OSError as exception:
        if exception.errno == errno.ENOENT:
            # Directory does not exist, so return empty list.
            maaslog.warning(
                "No boot images have been imported from the region."
            )
            return []

        # Other error. Propagate.
        raise

    # Starting point for iteration: paths that contain only the
    # top-level subdirectory of tftproot, i.e. the architecture name.
    paths = [[subdir] for subdir in potential_osystems]

    # Extend paths deeper into the filesystem, through the levels that
    # represent architecture, sub-architecture, release, and label.
    # Any directory that doesn't extend this deep isn't a boot image.
    for level in ["arch", "subarch", "release", "label"]:
        paths = drill_down(tftproot, paths)

    # Include bootloaders
    if "bootloader" in potential_osystems:
        bootloader_paths = [["bootloader"]]
        for level in ["bootloader_type", "arch"]:
            bootloader_paths = drill_down(tftproot, bootloader_paths)
        paths += bootloader_paths

    # Get hold of image meta-data stored in the maas.meta file.
    metadata = get_image_metadata(tftproot)

    # Each path we find this way should be a boot image.
    # This gets serialised to JSON, so we really have to return a list, not
    # just any iterable.
    return list(
        chain.from_iterable(
            extract_image_params(path, metadata) for path in paths
        )
    )


def get_image_metadata(tftproot):
    meta_file_path = maas_meta_file_path(tftproot)
    try:
        with open(meta_file_path, encoding="utf-8") as f:
            metadata = f.read()
    except OSError as e:
        if e.errno != errno.ENOENT:
            # Unexpected error, propagate.
            raise
        # No meta file (yet), it means no import has run so just skip
        # it.
        metadata = ""

    return metadata
