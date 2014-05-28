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
from os import makedirs
import os.path
from subprocess import check_call
from textwrap import dedent

from provisioningserver import config
from provisioningserver.auth import MAAS_USER_GPGHOME


logger = getLogger(__name__)


def make_maas_own_boot_resources():
    """Upgrade hook: make the `maas` user the owner of the boot resources."""
    # This reduces the privileges required for importing and managing images.
    if os.path.isdir(config.BOOT_RESOURCES_STORAGE):
        check_call(['chown', '-R', 'maas', config.BOOT_RESOURCES_STORAGE])


def create_gnupg_home():
    """Upgrade hook: create maas user's GNUPG home directory."""
    if not os.path.isdir(MAAS_USER_GPGHOME):
        makedirs(MAAS_USER_GPGHOME)
        check_call(['chown', 'maas:maas', MAAS_USER_GPGHOME])


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


# Upgrade hooks, from oldest to newest.  The hooks are callables, taking no
# arguments.  They are called in order.
#
# Each hook figures out for itself whether its changes are needed.  There is
# no record of previous upgrades.
UPGRADE_HOOKS = [
    make_maas_own_boot_resources,
    create_gnupg_home,
    retire_bootresources_yaml,
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
