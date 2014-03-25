# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Management command: upgrade the cluster.

This module implements the `ActionScript` interface for pserv commands.

Use the upgrade-cluster command when the MAAS code has been updated (e.g. while
installing a package ugprade, from the packaging) to perform any data
migrations that the new version may require.

This maintains a list of upgrade hooks, each representing a data migration
that was needed at some point in development of the MAAS cluster codebase.
All these hooks get run, in chronological order.  There is no record of
updates that have already been performed; each hook figures out for itself
whether its migration is needed.

Backwards migrations are not supported.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'add_arguments',
    'run',
    ]

from logging import getLogger
from os import (
    listdir,
    readlink,
    remove,
    renames,
    symlink,
    )
import os.path
from shutil import rmtree

from provisioningserver.config import Config
from provisioningserver.utils import (
    ensure_dir,
    locate_config,
    )


logger = getLogger(__name__)


def list_dirs(parent_dir):
    """List just the directories in `parent_dir`, as full paths.

    Includes symlinks to directories.
    """
    return sorted(
        os.path.join(parent_dir, entry)
        for entry in listdir(parent_dir)
        if os.path.isdir(os.path.join(parent_dir, entry)))


def is_image_dir(path):
    """Does `path` seem to be a boot image directory?"""
    if len(list_dirs(path)) > 0:
        # Nope.  It's got directories in it.  We're probably looking at a
        # "label" dir.
        return False
    for filename in os.listdir(path):
        if 'linux' in filename or 'initrd' in filename:
            # Looks like a kernel or initrd.  This could well be an image.
            return True
    return False


def gather_legacy_images(tftproot):
    """Collect a list of legacy boot-image paths.

    Supports the `add_label_directory_level_to_boot_images` upgrade hook.

    :param tftproot: The TFTP root directory containing the images.
    :return: A list of legacy image paths relative to `tftproot`.
    """
    tftproot = os.path.normpath(tftproot)
    legacy_images = []
    for arch_dir in list_dirs(tftproot):
        for subarch_dir in list_dirs(arch_dir):
            for release_dir in list_dirs(subarch_dir):
                for possible_image in list_dirs(release_dir):
                    if is_image_dir(possible_image):
                        legacy_images.append(possible_image)

    return [
        os.path.relpath(image, tftproot)
        for image in legacy_images
        ]


def move_real_boot_image(tftproot, legacy_image):
    """Move "real" "legacy" boot image to its "modern" location.

    Supports the `add_label_directory_level_to_boot_images` upgrade hook.

    Use this on a boot image that is an actual directory, but not for a
    symlink to another image.  For those, use `move_linked_boot_image`.

    The "modern" location has an additional `label` directory level.  For a
    legacy image, the label will be `release`.  If the "modern" version of
    the image already exists, the legacy image is simply deleted.

    :param tftproot: The TFTP root directory containing the images.
    :param legacy_image: Path to the image, relative to `tftproot`.
    """
    legacy_path = os.path.join(tftproot, legacy_image)
    assert not os.path.islink(legacy_path)
    [arch, subarch, release, purpose] = legacy_image.split(os.path.sep)
    label = 'release'
    modern_path = os.path.join(
        tftproot, arch, subarch, release, label, purpose)
    if os.path.isdir(modern_path):
        # Modern image already exists.  Just delete the legacy image.
        rmtree(legacy_path)
    else:
        # Move the legacy image into place.
        renames(legacy_path, modern_path)


def move_linked_boot_image(tftproot, legacy_image):
    """Move "legacy" boot image symlink to its "modern" location.

    Supports the `add_label_directory_level_to_boot_images` upgrade hook.

    Use this on a boot image that is a symlink to an actual boot image
    directory.  For the boot image directories themselves, use
    `move_real_boot_image`.

    The "modern" location has an additional `label` directory level.  For a
    legacy image, the label will be `release`.  If the "modern" version of
    the image already exists, the legacy image is simply deleted.

    Three kinds of symlink are supported: relative ones to other images in the
    same directory, absolute ones pointing to another image in the same
    directory but with a different boot purpose, and absolute ones pointing
    elsewhere.  Relative symlinks pointing to any other directory than where
    the link itself is are not supported and will be kept as-is.  Absolute
    links pointing to "legacy" images in the same tree will be updated to
    point to the corresponding "modern" images.

    :param tftproot: The TFTP root directory containing the images.
    :param legacy_image: Path to the image, relative to `tftproot`.
    """
    legacy_path = os.path.join(tftproot, legacy_image)
    assert os.path.islink(legacy_path)
    [arch, subarch, release, purpose] = legacy_image.split(os.path.sep)
    label = 'release'
    modern_path = os.path.join(
        tftproot, arch, subarch, release, label, purpose)
    if os.path.isdir(modern_path):
        # Modern image already exists.  Just delete the link.
        remove(legacy_path)
        return

    dest = os.path.normpath(readlink(legacy_path))
    if os.path.sep not in dest:
        # Easy!  It's a relative link into the same directory, as might happen
        # for an alternate purpose.  Just move it.
        ensure_dir(os.path.dirname(modern_path))
        renames(legacy_path, modern_path)
        return

    if not dest.startswith(os.path.sep):
        # Relative link, but not to the same directory.  Too confusing; don't
        # touch it.
        logger.warn(
            "Not migrating confusing link %s (to %s). If this is a boot "
            "image, move it manually or re-import boot images.",
            legacy_path, dest)
        return

    # From here on we know we're dealing with an absolute symlink.

    if not dest.startswith(os.path.normpath(tftproot) + os.path.sep):
        # Easy!  This is an absolute link to a directory outside the images
        # directory.  Just move it as-is.
        ensure_dir(os.path.dirname(modern_path))
        renames(legacy_path, modern_path)
        return

    path_elements = os.path.relpath(dest, tftproot).split(os.path.sep)
    if len(path_elements) != len(['arch', 'subarch', 'release', 'purpose']):
        # This is an absolute link to somewhere in the TFTP root directory, but
        # it doesn't look as if it points to a regular boot image.  Don't know
        # what to do with this, so leave it alone.
        logger.warn(
            "Not migrating confusing link %s (to %s). If this is a boot "
            "image, move it manually or re-import boot images.",
            legacy_path, dest)
        return

    # At this point we're pretty sure we have an absolute link to a legacy boot
    # image, at the right depth in the directory tree.  Build a new one,
    # pointing to the modern path for that image.
    [arch, subarch, release, purpose] = path_elements
    label = 'release'
    modern_real_path = os.path.join(
        os.path.normpath(tftproot), arch, subarch, release, label, purpose)
    ensure_dir(os.path.dirname(modern_path))
    symlink(modern_real_path, modern_path)
    remove(legacy_path)


# TODO: Fill out revision and release data in docstring.
def add_label_directory_level_to_boot_images():
    """Upgrade hook: insert a "label" level into the boot images dir tree.

    Change landed in MAAS 1.5, 2014-03-??, r???.

    Before this upgrade, boot images were stored in the filesystem following
    a directory structure like:

        `<tftproot>/<arch>/<subarch>/<release>/<purpose>/`

    The upgrade adds a `label` directory level below `release`:

        `<tftproot>/<arch>/<subarch>/<release>/<label>/<purpose>/`

    This hook looks for the old-style layout, and moves any legacy images to
    their respective places in the new layout.
    """
    tftproot = Config.load_from_cache()['tftp']['root']
    if not os.path.isdir(tftproot):
        # TFTP root directory does not exist.  There are no images yet.
        return

    legacy_images = gather_legacy_images(tftproot)
    if len(legacy_images) == 0:
        return
    logger.info(
        "Adding 'label' directory level to legacy boot images: %s",
        ', '.join(legacy_images))
    for image in legacy_images:
        if os.path.islink(os.path.join(tftproot, image)):
            move_linked_boot_image(tftproot, image)
        else:
            move_real_boot_image(tftproot, image)


def rewrite_boot_resources_config(config_file):
    """Rewrite the `bootresources.yaml` configuration."""


def generate_boot_resources_config():
    """Upgrade hook: rewrite `bootresources.yaml` based on boot images.

    This finds boot images downloaded into the old, pre-Simplestreams tftp
    root, and writes a boot-resources configuration to import a similar set of
    images using Simplestreams.
    """
    config_file = locate_config('bootresources.yaml')
    boot_resources = Config.load_from_cache(config_file)
    if not boot_resources['boot'].get('configure_me', False):
        # Already configured.
        return
    rewrite_boot_resources_config(config_file)


# Upgrade hooks, from oldest to newest.  The hooks are callables, taking no
# arguments.  They are called in order.
#
# Each hook figures out for itself whether its changes are needed.  There is
# no record of previous upgrades.
UPGRADE_HOOKS = [
    add_label_directory_level_to_boot_images,
    generate_boot_resources_config,
    ]


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    # This command accepts no arguments.


# The docstring for the "run" function is also the command's documentation.
def run(args):
    """Perform any data migrations needed for upgrading this cluster."""
    for hook in UPGRADE_HOOKS:
        hook()
