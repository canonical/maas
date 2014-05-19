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

from provisioningserver.auth import MAAS_USER_GPGHOME
from provisioningserver.import_images import boot_resources


logger = getLogger(__name__)


def make_maas_own_boot_resources():
    """Upgrade hook: make the `maas` user the owner of the boot resources."""
    # This reduces the privileges required for importing and managing images.
    config = boot_resources.read_config()
    storage_dir = config['boot']['storage']
    if os.path.isdir(storage_dir):
        check_call(['chown', '-R', 'maas', storage_dir])


def create_gnupg_home():
    """Upgrade hook: create maas user's GNUPG home directory."""
    if not os.path.isdir(MAAS_USER_GPGHOME):
        makedirs(MAAS_USER_GPGHOME)
        check_call(['chown', 'maas:maas', MAAS_USER_GPGHOME])


# Upgrade hooks, from oldest to newest.  The hooks are callables, taking no
# arguments.  They are called in order.
#
# Each hook figures out for itself whether its changes are needed.  There is
# no record of previous upgrades.
UPGRADE_HOOKS = [
    make_maas_own_boot_resources,
    create_gnupg_home,
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
