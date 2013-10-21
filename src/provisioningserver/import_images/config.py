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
    'EPHEMERALS_LEGACY_CONFIG',
    'merge_legacy_ephemerals_config',
    'retire_legacy_config',
    ]


from copy import deepcopy
from os import rename
import os.path
from pipes import quote

from provisioningserver.utils import (
    call_capture_and_check,
    filter_dict,
    )

# Legacy shell-style config file for the ephemerals config.
EPHEMERALS_LEGACY_CONFIG = '/etc/maas/import_ephemerals'

# Legacy configuration options for the old ephemerals import script.
#
# REMOTE_IMAGES_MIRROR is no longer relevant, since we are using a new data
# format. If people were running their own mirrors, presumably they'll set
# up new simplestreams mirrors which probably won't have the same path.
#
# TARBALL_CACHE_D could be where we stick our cache of the simplestreams
# data, although for now it is unused.
EPHEMERALS_LEGACY_OPTIONS = {
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
    source_config = 'source %s >/dev/null' % quote(EPHEMERALS_LEGACY_CONFIG)
    export_vars = 'export ' + ' '.join(quote(var) for var in options)
    dump_env = 'env -0'
    shell_code = '; '.join([source_config, export_vars, dump_env])
    output = call_capture_and_check(['bash', '-c', shell_code])
    # Assume UTF-8 encoding.  If the system uses something else but the
    # variables are all ASCII, that's probably fine too.
    output = output.decode('utf-8')

    variables = dict(
        setting.split('=', 1)
        for setting in output.split('\0')
        if len(setting) > 0)

    return filter_dict(variables, options)


def merge_legacy_ephemerals_config(config):
    """Update `config` based on legacy shell-script config (if any).

    :return: Whether the configuration has been updated.
    """
    loaded_boot_config = deepcopy(config['boot'])

    legacy_config = parse_legacy_config(EPHEMERALS_LEGACY_OPTIONS)
    if len(legacy_config) == 0:
        return False

    arches = legacy_config.get('ARCHES', '')
    arches = ' '.join(arch.split("/")[0] for arch in arches.split())
    data_dir = legacy_config.get('DATA_DIR')
    releases = legacy_config.get('RELEASES')
    if arches is not None:
        config['boot']['architectures'] = arches.split()
    if data_dir is not None:
        config['boot']['ephemeral']['images_directory'] = data_dir
    if releases is not None:
        config['boot']['ephemeral']['releases'] = releases.split()

    return config['boot'] != loaded_boot_config


def retire_legacy_config():
    """Rename the legacy config file so we don't convert it again."""
    rename(EPHEMERALS_LEGACY_CONFIG, EPHEMERALS_LEGACY_CONFIG + '.obsolete')
