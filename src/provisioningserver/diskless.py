# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate diskless image for system to boot."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'create_diskless_disk',
    'delete_diskless_disk',
    ]

import os
from textwrap import dedent

from provisioningserver import config
from provisioningserver.drivers.diskless import DisklessDriverRegistry
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystemRegistry,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.fs import (
    atomic_symlink,
    atomic_write,
)
from provisioningserver.utils.shell import call_and_check


maaslog = get_maas_logger("diskless")


class DisklessError(Exception):
    """Error raised when issue occurs during a diskless task."""


def get_diskless_store():
    """Return path to the diskless store.

    This is the location that all diskless links exist. It holds all of the
    currently in use disk for diskless booting.
    """
    return os.path.join(
        config.BOOT_RESOURCES_STORAGE, 'diskless', 'store')


def compose_diskless_link_path(system_id):
    """Return path to the symbolic link for the given system_id.

    This is the link that will be written into the diskless store. It is used
    to reference what disks are currently being used for diskless booting.
    """
    return os.path.join(get_diskless_store(), system_id)


def create_diskless_link(system_id, storage_path):
    """Create symbolic link in the diskless store to the actual path
    of the backing store.

    Each diskless driver returns an absolute path to were the data can be
    accessed on the system. A symbolic link is made in the diskless store to
    reference this location, so it can be retrieved later by system_id.
    """
    link_path = compose_diskless_link_path(system_id)
    if os.path.lexists(link_path):
        raise DisklessError(
            "Backend storage link already exists for: %s" % system_id)
    atomic_symlink(storage_path, link_path)


def delete_diskless_link(system_id):
    """Delete symbolic link in the diskless store."""
    link_path = compose_diskless_link_path(system_id)
    if os.path.lexists(link_path):
        os.unlink(link_path)


def read_diskless_link(system_id):
    """Return actual path to the backing store, from the link
    in the diskless store."""
    link_path = compose_diskless_link_path(system_id)
    if not os.path.lexists(link_path):
        return None
    return os.readlink(link_path)


def get_diskless_target(system_id):
    """Get the iscsi target name for the node."""
    prefix = 'iqn.2004-05.com.ubuntu:maas'
    return '%s:root-diskless-%s' % (prefix, system_id)


def get_diskless_tgt_path():
    """Return path to maas-diskless.tgt."""
    return os.path.join(
        config.BOOT_RESOURCES_STORAGE, 'diskless', 'maas-diskless.tgt')


def tgt_entry(system_id, image):
    """Generate tgt target used for root disk

    Tgt target used by the node as its root disk. This function creates target
    description in a format used by tgt-admin. It uses system_id to generate
    target name and image as a path to image file which should be available.

    :param system_id: Node system_id
    :param image: Path to the image which should be shared via tgt/iscsi
    :return Tgt entry which can be written to tgt-admin configuration file
    """
    target = get_diskless_target(system_id)
    entry = dedent("""\
        <target {target}>
            readonly 0
            backing-store "{image}"
            driver iscsi
        </target>
        """).format(target=target, image=image)
    return entry


def compose_diskless_tgt_config():
    """Produce the contents of a diskless tgt conf file.

    :return: Contents for a `targets.conf` file.
    :rtype: bytes
    """
    tgt_entries = []
    for system_id in os.listdir(get_diskless_store()):
        image_path = compose_diskless_link_path(system_id)
        tgt_entries.append(tgt_entry(system_id, image_path))
    return ''.join(tgt_entries).encode('utf-8')


def reload_diskless_tgt():
    """Reload the diskless tgt config."""
    call_and_check([
        'sudo',
        '/usr/sbin/tgt-admin',
        '--conf', get_diskless_tgt_path(),
        '--update', 'ALL',
        ])


def update_diskless_tgt():
    """Re-writes the "maas-diskless.tgt" to include all targets that have
    symlinks in the diskless store. Reloads the tgt config."""
    tgt_path = get_diskless_tgt_path()
    tgt_config = compose_diskless_tgt_config()
    atomic_write(tgt_config, tgt_path, mode=0644)
    reload_diskless_tgt()


def get_diskless_driver(driver):
    """Return the diskless driver object.

    :raise DisklessError: if driver does not exist.
    """
    driver_obj = DisklessDriverRegistry.get_item(driver)
    if driver_obj is None:
        raise DisklessError(
            "Cluster doesn't support diskless driver: %s" % driver)
    return driver_obj


def compose_source_path(osystem_name, arch, subarch, release, label):
    """Return path to the source file for the diskless boot image.

    Each diskless driver will use this source to initialize the disk.
    """
    osystem = OperatingSystemRegistry.get_item(osystem_name)
    if osystem is None:
        raise DisklessError(
            "OS doesn't exist in operating system registry: %s" % osystem_name)
    purposes = osystem.get_boot_image_purposes(arch, subarch, release, label)
    if BOOT_IMAGE_PURPOSE.DISKLESS not in purposes:
        raise DisklessError(
            "OS doesn't support diskless booting: %s" % osystem_name)
    root_path, _ = osystem.get_xinstall_parameters()
    return os.path.join(
        config.BOOT_RESOURCES_STORAGE, 'current',
        osystem_name, arch, subarch, release, label, root_path)


def create_diskless_disk(driver, driver_options, system_id,
                         osystem, arch, subarch, release, label):
    """Creates a disk using the `driver` for the `system_id`. This disk will
    be used for booting diskless."""
    source_path = compose_source_path(osystem, arch, subarch, release, label)
    if not os.path.exists(source_path):
        raise DisklessError("Boot resources doesn't exist: %s" % source_path)
    link_path = compose_diskless_link_path(system_id)
    if os.path.lexists(link_path):
        raise DisklessError("Disk already exists for node: %s" % system_id)

    # Create the disk with the driver, and place the link in diskless source.
    maaslog.info(
        "Creating disk for node %s using driver: %s", system_id, driver)
    driver_obj = get_diskless_driver(driver)
    disk_path = driver_obj.create_disk(
        system_id, source_path, **driver_options)
    if disk_path is None or not os.path.exists(disk_path):
        raise DisklessError(
            "Driver failed to create disk for node: %s" % system_id)
    create_diskless_link(system_id, disk_path)

    # Re-write the tgt config, to include the new disk for the node.
    maaslog.info("Updating iSCSI targets.")
    update_diskless_tgt()


def delete_diskless_disk(driver, driver_options, system_id):
    """Deletes the disk that was used by the node for diskless booting."""
    link_path = compose_diskless_link_path(system_id)
    if not os.path.lexists(link_path):
        maaslog.warn("Disk already deleted for node: %s", system_id)
        return

    maaslog.info(
        "Destroying disk for node %s using driver: %s", system_id, driver)
    disk_path = read_diskless_link(system_id)
    if disk_path is None:
        raise DisklessError(
            "Failed to read diskless link for node: %s" % system_id)
    if os.path.exists(disk_path):
        driver_obj = get_diskless_driver(driver)
        driver_obj.delete_disk(system_id, disk_path, **driver_options)
    else:
        maaslog.warn((
            "Assuming disk has already been removed "
            "for node %s by the driver: %s"), system_id, driver)
    delete_diskless_link(system_id)

    # Re-write the tgt config, to include only the remaining disks.
    maaslog.info("Updating iSCSI targets.")
    update_diskless_tgt()
