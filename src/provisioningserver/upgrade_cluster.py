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

# Upgrade hooks, from oldest to newest.  The hooks are callables, taking no
# arguments.  They are called in order.
#
# Each hook figures out for itself whether its changes are needed.  There is
# no record of previous upgrades.
UPGRADE_HOOKS = []


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
