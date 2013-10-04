# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration handling for import scripts."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'load_ephemerals_config',
    ]


import os.path
from subprocess import check_output

import distro_info
from provisioningserver.config import Config
from provisioningserver.import_images.tgt import TARGET_NAME_PREFIX
from provisioningserver.utils import (
    atomic_write,
    filter_dict,
    )
import yaml

# Default settings for various options.
DEFAULTS = {
    'directory': "/var/lib/maas/ephemeral",
    'arches': ["amd64", "i386", "armhf"],
    'releases': distro_info.UbuntuDistroInfo().supported(),
    'target_name_prefix': TARGET_NAME_PREFIX,
}


# Mapping of option names to their legacy, shell-style config equivalents.
EPHEMERALS_LEGACY_OPTIONS = {
    'directory': 'DATA_DIR',
    'arches': 'ARCHES',
    'releases': 'RELEASES',
    'target_name_prefix': 'TARGET_NAME_PREFIX',
}


# Legacy shell-style config file for the ephemerals config.
EPHEMERALS_LEGACY_CONFIG = '/etc/maas/import_ephemerals'

# Configuration options for the ephemerals import script.
#
# REMOTE_IMAGES_MIRROR is no longer relevant, since we are using a new data
# format. If people were running their own mirrors, presumably they'll set
# up new simplestreams mirrors which probably won't have the same path.
#
# TARBALL_CACHE_D could be where we stick our cache of the simplestreams
# data, although for now it is unused.
EPHEMERALS_OPTIONS = {
    'TARGET_NAME_PREFIX',
    'DATA_DIR',
    'RELEASES',
    'ARCHES',
    'TARBALL_CACHE_D',
    }


def parse_legacy_config(options):
    """Parse an old-style, shell-script configuration.

    This runs the config file (if it exists) in a shell.

    :param: A container of option names that should be read from the config.
    :return: A dict mapping variable names to values, both as unicode.
        Any options that are not set by the config are left out.  Options that
        are set to the empty string come out as empty strings.
    """
    if not os.path.exists(EPHEMERALS_LEGACY_CONFIG):
        return {}

    # Source the legacy settings file, and print the environment.  Use the nul
    # character as a separator, so we don't get confused by newlines in the
    # values.
    output = check_output([
        'bash', '-c',
        'source %s >/dev/null; env -0' % EPHEMERALS_LEGACY_CONFIG,
        ])
    # Assume UTF-8 encoding.  If the system uses something else but the
    # variables are all ASCII, that's probably fine too.
    output = output.decode('utf-8')

    variables = dict(
        setting.split('=', 1)
        for setting in output.split('\0')
            if len(setting) > 0)

    return filter_dict(variables, options)


def maybe_update_config(config):
    """Update the config if it doesn't have values from the old config.

    :return: Whether the configuration has been updated.
    """
    if config['boot']['ephemeral'].get('target_name_prefix') is not None:
        # The config we have is nonempty.  If there was any legacy config to
        # port, we've already done it.
        return False

    old = parse_legacy_config(EPHEMERALS_OPTIONS)
    if len(old) == 0:
        # The legacy config is empty.  There may be a problem, so don't rewrite
        # our non-legacy config.
        # TODO: Log this.
        return False

    eph = config['boot']['ephemeral']
    for option, legacy_option in EPHEMERALS_LEGACY_OPTIONS.iteritems():
        eph[option] = old.get(legacy_option) or DEFAULTS[option]

    return True


def load_ephemerals_config():
    """Load config for the ephemerals import script.

    If there is no configuration yet, this attempts to import a legacy-style
    shell-script configuration.
    """
    current = Config.load()

    changed = maybe_update_config(current)
    if changed:
        atomic_write(yaml.safe_dump(current), Config.DEFAULT_FILENAME)

    return Config.load()
