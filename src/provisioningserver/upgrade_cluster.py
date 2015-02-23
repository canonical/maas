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

import os
from os import makedirs
import shutil
from subprocess import check_call
from textwrap import dedent

from provisioningserver.cluster_config import get_boot_resources_storage
from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.boot.tftppath import (
    drill_down,
    list_subdirs,
    )
from provisioningserver.import_images.boot_resources import (
    update_targets_conf,
    write_targets_conf,
    )
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("cluster_upgrade")


def make_maas_own_boot_resources():
    """Upgrade hook: make the `maas` user the owner of the boot resources."""
    # This reduces the privileges required for importing and managing images.
    if os.path.isdir(get_boot_resources_storage()):
        check_call(['chown', '-R', 'maas', get_boot_resources_storage()])


def create_gnupg_home():
    """Upgrade hook: create maas user's GNUPG home directory."""
    gpghome = get_maas_user_gpghome()
    if not os.path.isdir(gpghome):
        makedirs(gpghome)
        if os.geteuid() == 0:
            # Make the maas user the owner of its GPG home.  Do this only if
            # running as root; otherwise it would probably fail.  We want to
            # be able to start a development instance without triggering that.
            check_call(['chown', 'maas:maas', gpghome])


# Path to obsolete boot-resources configuration.
BOOTRESOURCES_FILE = '/etc/maas/bootresources.yaml'

# Recognisable header, to be prefixed to BOOTRESOURCES_FILE as part of the
# warning that the file is obsolete.  The retire_bootresources_yaml upgrade
# hook will prefix this header and further details to the file, if and only
# if this header is not yet present.
BOOTRESOURCES_HEADER = "# THIS FILE IS OBSOLETE."

# Warning, to be prefixed to BOOTRESOURCES_FILE as an indication that the
# file is obsolete.
BOOTRESOURCES_WARNING = BOOTRESOURCES_HEADER + '\n' + dedent("""\
    #
    # The configuration below is no longer in use, and can be removed.
    # By default, cluster controllers now import images for all supported
    # Ubuntu LTS releases in all supported architectures.
    #
    # Imports can now be configured through the MAAS region controller API:
    # See http://maas.ubuntu.com/docs/api.html#boot-source
    #
    # To do this, define a boot source through a POST to the nodegroup's
    # boot-sources endpoint
    # (e.g. http://<server>/api/1.0/nodegroups/<uuid>/boot-sources), and then
    # POST to the resulting boot source to define selections.  Each cluster
    # can have any number of boot sources, and each boot source can have any
    # number of selections, as in the old configuration.
    #
    # The same thing can be done using the command-line front-end for the API.
    # After logging in to the MAAS to create a profile, run:
    #
    # maas <my-profile> boot-sources create <cluster-uuid>\
    url=<path> keyring_filename=<keyring>
    #
    # Here,
    #  * <my-profile> is your login profile in the 'maas' command.
    #  * <cluster-uuid> is the UUID of the cluster.
    #  * <path> is the source's path as found in this config file.
    #  * <keyring> is the keyring entry as found in this config file.
    #
    # Full documentation can be found at http://maas.ubuntu.com/docs/
    #
    # The maas-import-pxe-files import script is now deprecated; use the
    # MAAS web UI, region-controller, or the "maas" command to trigger any
    # manual imports.
    #
    # If you do wish to continue using maas-import-pxe-files for the time
    # being, the script now requires a sources definition consisting of
    # just the contents of the "sources" section as found in this
    # configuration file.  See the script's man page for an example.
    """) + '\n'


def retire_bootresources_yaml():
    """Upgrade hook: mark `/etc/maas/bootresources.yaml` as obsolete.

    Prefixes `BOOTRESOURCES_WARNING` to the config file, if present.

    This file was temporarily used in MAAS 1.5 to let users restrict which
    boot resources should be downloaded, where from, and to where in the
    filesystem.  The settings have been replaced with model classes.
    """
    if not os.path.isfile(BOOTRESOURCES_FILE):
        return
    header = BOOTRESOURCES_HEADER.encode('ascii')
    warning = BOOTRESOURCES_WARNING.encode('ascii')
    with open(BOOTRESOURCES_FILE, 'r+b') as old_config:
        old_contents = old_config.read()
        if old_contents.startswith(header):
            # Warning is already there.
            return
        old_config.seek(0)
        old_config.write(warning)
        old_config.write(old_contents)


def filter_out_directories_with_extra_levels(paths):
    """Remove paths that contain directories with more levels. We don't want
    to move other operating systems under the ubuntu directory."""
    for arch, subarch, release, label in paths:
        path = os.path.join(
            get_boot_resources_storage(),
            arch, subarch, release, label)
        if len(list_subdirs(path)) == 0:
            yield (arch, subarch, release, label)


def migrate_architectures_into_ubuntu_directory():
    """Upgrade hook: move architecture folders under the ubuntu folder.

    With the support of multiple operating systems the structure of the
    boot resources directory added another level to the hierarchy. Previously
    the hierarchy was arch/subarch/release/label, it has now been modified to
    os/arch/subarch/release/label.

    Before multiple operating systems only Ubuntu was supported. Check if
    folders have structure arch/subarch/release/label and move them into
    ubuntu folder. Making the final path ubuntu/arch/subarch/release/label.
    """
    current_dir = os.path.join(get_boot_resources_storage())
    if not os.path.isdir(current_dir):
        return
    # If ubuntu folder already exists, then no reason to continue
    if 'ubuntu' in list_subdirs(current_dir):
        return

    # Starting point for iteration: paths that contain only the
    # top-level subdirectory of tftproot, i.e. the architecture name.
    potential_arches = list_subdirs(current_dir)
    paths = [[subdir] for subdir in potential_arches]

    # Extend paths deeper into the filesystem, through the levels that
    # represent sub-architecture, release, and label.
    # Any directory that doesn't extend this deep isn't a boot image.
    for level in ['subarch', 'release', 'label']:
        paths = drill_down(current_dir, paths)
    paths = filter_out_directories_with_extra_levels(paths)

    # Extract the only top directories (arch) from the paths, as we only need
    # its name to move into the new 'ubuntu' folder.
    arches = {arch for arch, _, _, _ in paths}
    if len(arches) == 0:
        return

    # Create the ubuntu directory and move the archiecture folders under that
    # directory.
    ubuntu_dir = os.path.join(current_dir, 'ubuntu')
    os.mkdir(ubuntu_dir)
    for arch in arches:
        shutil.move(os.path.join(current_dir, arch), ubuntu_dir)

    # Re-write the maas.tgt to point to the new location for the ubuntu boot
    # resources.
    write_targets_conf(current_dir)
    update_targets_conf(current_dir)


# Upgrade hooks, from oldest to newest.  The hooks are callables, taking no
# arguments.  They are called in order.
#
# Each hook figures out for itself whether its changes are needed.  There is
# no record of previous upgrades.
UPGRADE_HOOKS = [
    make_maas_own_boot_resources,
    create_gnupg_home,
    retire_bootresources_yaml,
    migrate_architectures_into_ubuntu_directory,
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
        maaslog.info("Cluster upgrade hook %s started." % hook.__name__)
        hook()
        maaslog.info("Cluster upgrade hook %s finished." % hook.__name__)
