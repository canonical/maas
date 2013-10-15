# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Management of iSCSI targets for the ephemerals import script."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'clean_up_info_file',
    'get_conf_path',
    'get_target_name',
    'set_up_data_dir',
    'tgt_admin_delete',
    'tgt_admin_update',
    'write_conf',
    'write_info_file',
    ]

import os
import os.path
import re
import shutil
from textwrap import dedent

from provisioningserver.kernel_opts import (
    ISCSI_TARGET_NAME_PREFIX,
    prefix_target_name,
    )
from provisioningserver.utils import (
    call_and_check,
    call_capture_and_check,
    ensure_dir,
    write_text_file,
    )

# Basic tgt-admin command line.
TGT_ADMIN = ["tgt-admin", "--conf", "/etc/tgt/targets.conf"]

# Template for the tgt.conf file in the data directory.
DATA_DIR_TGT_CONF_TEMPLATE = dedent("""\
    include {path}/*.conf
    default-driver iscsi
    """)

# Template for individual tgt.conf files in target directories.
TGT_CONF_TEMPLATE = dedent("""\
    <target {prefix}:{{target_name}}>
        readonly 1
        backing-store "{{image}}"
    </target>
    """).format(prefix=ISCSI_TARGET_NAME_PREFIX)

INFO_TEMPLATE = dedent("""\
    release={release}
    label={label}
    serial={serial}
    arch={arch}
    name={name}
    """)


def tgt_conf_d(data_dir):
    """Return the path of a data directory's configuration directory."""
    return os.path.abspath(os.path.join(data_dir, 'tgt.conf.d'))


def get_conf_path(data_dir, config_name):
    """Return the path for an iSCSI config file.

    :param data_dir: Base data directory.  The config should be in its
        `tgt.conf.d` subdirectory.
    :param config_name: Base name for the config.  A ".conf" suffix will be
        added.
    """
    return os.path.join(tgt_conf_d(data_dir), "%s.conf" % config_name)


def get_target_name(release, version, arch, version_name):
    """Compose a target's name based on its parameters.

    The `**kwargs` are inert.  They are only here for calling convenience.
    """
    return '-'.join(['maas', release, version, arch, version_name])


def tgt_admin_delete(name):
    """Delete a target using `tgt-admin`."""
    call_and_check(TGT_ADMIN + ["--delete", prefix_target_name(name)])


class TargetNotCreated(RuntimeError):
    """tgt-admin failed to create a target."""


def target_exists(full_name):
    """Run `tgt --show` to determine whether the given target exists.

    :param full_name: Full target name, including `ISCSI_TARGET_NAME_PREFIX`.
    :return: bool.
    """
    status = call_capture_and_check(TGT_ADMIN + ["--show"])
    regex = b'^Target [0-9]+: %s\\s*$' % re.escape(full_name).encode('ascii')
    match = re.search(regex, status, flags=re.MULTILINE)
    return match is not None


def tgt_admin_update(target_dir, target_name):
    """Update a target using `tgt-admin`.

    Actually we use this to add new targets.
    """
    full_name = prefix_target_name(target_name)
    call_and_check(TGT_ADMIN + ["--update", full_name])
    # Check that the target was really created.
    # Reportedly tgt-admin tends to return 0 even when it fails, so check
    # actively.
    if not target_exists(full_name):
        raise TargetNotCreated("Failed tgt-admin add for %s" % full_name)


def set_up_data_dir(data_dir):
    """Create a data directory and its configuration directory."""
    ensure_dir(tgt_conf_d(data_dir))
    write_text_file(
        os.path.join(data_dir, 'tgt.conf'),
        DATA_DIR_TGT_CONF_TEMPLATE.format(path=tgt_conf_d(data_dir)))


def write_info_file(target_dir, target_name, release, label, serial, arch):
    """Write the `info` file based on the given parameters."""
    text = INFO_TEMPLATE.format(
        release=release, label=label, serial=serial, arch=arch,
        name=target_name)
    info_file = os.path.join(target_dir, 'info')
    write_text_file(info_file, text)


def clean_up_info_file(target_dir):
    """To be called in the event of failure: move `info` file out of the way.

    The `info` file will be renamed `info.failed`, in the same directory, and
    any previously existing `info.failed` file is removed.
    """
    info_file = os.path.join(target_dir, 'info')
    if not os.path.exists(info_file):
        return
    failed_file = info_file + '.failed'
    if os.path.isfile(failed_file):
        os.remove(failed_file)
    shutil.move(info_file, failed_file)


def write_conf(path, target_name, image):
    """Write a `tgt.conf` file."""
    text = TGT_CONF_TEMPLATE.format(target_name=target_name, image=image)
    write_text_file(path, text)
