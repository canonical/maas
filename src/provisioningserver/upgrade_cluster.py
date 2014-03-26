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
import os.path

from provisioningserver.config import Config
from provisioningserver.pxe.tftppath import drill_down
from provisioningserver.utils import locate_config


logger = getLogger(__name__)


def find_old_imports(tftproot):
    """List pre-Simplestreams boot images.

    Supports the `generate_boot_resources_config` upgrade hook.  Returns a set
    of tuples (arch, subarch, release) describing all of the images found.
    """
    if not os.path.isdir(tftproot):
        return set()
    paths = [[tftproot]]
    for level in ['arch', 'subarch', 'release', 'purpose']:
        paths = drill_down(tftproot, paths)
    return {
        (arch, subarch, release)
        for [root, arch, subarch, release, purpose] in paths
        }


def rewrite_boot_resources_config(config_file):
    """Rewrite the `bootresources.yaml` configuration."""
    tftproot = Config.load_from_cache()['tftp']['root']
    old_images = find_old_imports(tftproot)
    old_images  # XXX jtv 2014-03-26: Turn into new config.


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
