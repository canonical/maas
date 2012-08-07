# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate kernel command-line options for inclusion in PXE configs."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'compose_kernel_command_line',
    ]

import os

from django.conf import settings
from maasserver.server_address import get_maas_facing_server_address
from maasserver.utils import absolute_reverse
from provisioningserver.pxe.tftppath import compose_image_path
from provisioningserver.utils import parse_key_value_file


def compose_initrd_opt(arch, subarch, release, purpose):
    path = "%s/initrd.gz" % compose_image_path(arch, subarch, release, purpose)
    return "initrd=%s" % path


def compose_enlistment_preseed_url():
    """Compose enlistment preseed URL."""
    # Always uses the latest version of the metadata API.
    version = 'latest'
    return absolute_reverse(
        'metadata-enlist-preseed', args=[version],
        query={'op': 'get_enlist_preseed'})


def compose_preseed_url(node):
    """Compose a metadata URL for `node`'s preseed data."""
    # Always uses the latest version of the metadata API.
    version = 'latest'
    return absolute_reverse(
        'metadata-node-by-id', args=[version, node.system_id],
        query={'op': 'get_preseed'})


def compose_preseed_opt(node):
    """Compose a kernel option for preseed URL for given `node`.

    :param mac_address: A `Node`, or `None`.
    """
    if node is None:
        preseed_url = compose_enlistment_preseed_url()
    else:
        preseed_url = compose_preseed_url(node)
    return "auto url=%s" % preseed_url


def compose_suite_opt(release):
    return "suite=%s" % release


def compose_hostname_opt(node):
    if node is None:
        # Not a known host; still needs enlisting.  Make up a name.
        hostname = 'maas-enlist'
    else:
        hostname = node.hostname
    return "hostname=%s" % hostname


def compose_domain_opt(node):
    # TODO: This is probably not enough!
    domain = 'local.lan'
    return "domain=%s" % domain


def compose_locale_opt():
    locale = 'en_US'
    return "locale=%s" % locale


def compose_logging_opts():
    return [
        'log_host=%s' % get_maas_facing_server_address(),
        'log_port=%d' % 514,
        'text priority=%s' % 'critical',
        ]


def get_last_directory(root):
    """Return the last directory from the directories in the given root.

    This is used to get the most recent ephemeral import directory.
    The ephemeral directories are named after the release date: 20120424,
    20120424, 20120301, etc. so fetching the last one (sorting by name)
    returns the most recent.
    """
    dirs = [
        os.path.join(root, directory) for directory in os.listdir(root)]
    dirs = filter(os.path.isdir, dirs)
    return sorted(dirs)[-1]


ISCSI_TARGET_NAME_PREFIX = "iqn.2004-05.com.ubuntu:maas"


def get_ephemeral_name(release, arch):
    """Return the name of the most recent ephemeral image.

    That information is read from the config file named 'info' in the
    ephemeral directory e.g:
    /var/lib/maas/ephemeral/precise/ephemeral/i386/20120424/info
    """
    root = os.path.join(settings.EPHEMERAL_ROOT, release, 'ephemeral', arch)
    filename = os.path.join(get_last_directory(root), 'info')
    name = parse_key_value_file(filename, separator="=")['name']
    return name


def compose_purpose_opts(release, arch, purpose):
    """Return the list of the purpose-specific kernel options."""
    if purpose == "commissioning":
        return [
            "iscsi_target_name=%s:%s" % (
                ISCSI_TARGET_NAME_PREFIX, get_ephemeral_name(release, arch)),
            "ip=dhcp",
            "ro root=LABEL=cloudimg-rootfs",
            "iscsi_target_ip=%s" % get_maas_facing_server_address(),
            "iscsi_target_port=3260",
            ]
    else:
        return [
            "netcfg/choose_interface=auto"
            ]


def compose_kernel_command_line(node, arch, subarch, purpose):
    """Generate a line of kernel options for booting `node`.

    Include these options in the PXE config file's APPEND argument.

    The node may be None, in which case it will boot into enlistment.
    """
    # XXX JeroenVermeulen 2012-08-06 bug=1013146: Stop hard-coding this.
    release = 'precise'

    options = [
        compose_initrd_opt(arch, subarch, release, purpose),
        compose_preseed_opt(node),
        compose_suite_opt(release),
        compose_hostname_opt(node),
        compose_domain_opt(node),
        compose_locale_opt(),
        ]
    options += compose_purpose_opts(release, arch, purpose)
    options += compose_logging_opts()
    return ' '.join(options)
