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
from provisioningserver.boot.tftppath import drill_down
from provisioningserver.config import (
    BootConfig,
    Config,
    )
from provisioningserver.import_images import boot_resources
from provisioningserver.utils import (
    atomic_write,
    locate_config,
    read_text_file,
    )
import yaml


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


def generate_selections(images):
    """Generate `selections` stanzas to match pre-existing boot images.

    Supports the `generate_boot_resources_config` upgrade hook.

    :param images: An iterable of (arch, subarch, release) tuples as returned
        by `find_old_imports`.
    :return: A list of dicts, each describing one `selections` stanza for the
        `bootresources.yaml` file.
    """
    if len(images) == 0:
        # No old images found.
        return None
    else:
        # Return one "selections" stanza per image.  This could be cleverer
        # and combine multiple architectures/subarchitectures, but there would
        # have to be a clear gain.  Simple is good.
        return [
            {
                'release': release,
                'arches': [arch],
                'subarches': [subarch],
            }
            for arch, subarch, release in sorted(images)
            ]


def generate_updated_config(config, old_images):
    """Return an updated version of a config dict.

    Supports the `generate_boot_resources_config` upgrade hook.

    This clears the `configure_me` flag, and replaces all sources'
    `selections` stanzas with ones based on the old boot images.

    :param config: A config dict, as loaded from `bootresources.yaml`.
    :param old_images: Old-style boot images, as returned by
        `find_old_imports`.  If `None`, the existing `selections` are left
        unchanged.
    :return: An updated version of `config` with the above changes.
    """
    config = config.copy()
    # Remove the configure_me item.  It's there exactly to tell us that we
    # haven't done this rewrite yet.
    del config['boot']['configure_me']
    if old_images is None:
        return config

    # If we found old images, rewrite the selections.
    if len(old_images) != 0:
        new_selections = generate_selections(old_images)
        for source in config['boot']['sources']:
            source['selections'] = new_selections
    return config


def extract_top_comment(input_file):
    """Return just the comment at the top of `input_file`.

    Supports the `generate_boot_resources_config` upgrade hook.
    """
    lines = []
    for line in read_text_file(input_file).splitlines():
        stripped_line = line.lstrip()
        if stripped_line != '' and not stripped_line.startswith('#'):
            # Not an empty line or comment any more.  Stop.
            break
        lines.append(line)
    return '\n'.join(lines) + '\n'


def update_config_file(config_file, new_config):
    """Replace configuration data in `config_file` with `new_config`.

    Supports the `generate_boot_resources_config` upgrade hook.

    The first part of the config file, up to the first text that isn't a
    comment, is kept intact.  The part after that is overwritten with YAML
    for the new configuration.
    """
    header = extract_top_comment(config_file)
    data = yaml.safe_dump(new_config, default_flow_style=False)
    content = (header + data).encode('utf-8')
    atomic_write(content, config_file, mode=0644)
    BootConfig.flush_cache(config_file)


def rewrite_boot_resources_config(config_file):
    """Rewrite the `bootresources.yaml` configuration.

    Supports the `generate_boot_resources_config` upgrade hook.
    """
    # Look for images using the old tftp root setting, not the tftp
    # resource_root setting.  The latter points to where the newer,
    # Simplestreams-based boot images live.
    # This should be the final use of the old tftp root setting.  After this
    # has run, it serves no more purpose.
    tftproot = Config.load_from_cache()['tftp']['root']
    config = BootConfig.load_from_cache(config_file)
    old_images = find_old_imports(tftproot)
    new_config = generate_updated_config(config, old_images)
    update_config_file(config_file, new_config)


def generate_boot_resources_config():
    """Upgrade hook: rewrite `bootresources.yaml` based on boot images.

    This finds boot images downloaded into the old, pre-Simplestreams tftp
    root, and writes a boot-resources configuration to import a similar set of
    images using Simplestreams.
    """
    config_file = locate_config('bootresources.yaml')
    boot_resources = BootConfig.load_from_cache(config_file)
    if boot_resources['boot'].get('configure_me', False):
        rewrite_boot_resources_config(config_file)


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
    generate_boot_resources_config,
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
