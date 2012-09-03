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
    'compose_kernel_command_line_new',
    'KernelParameters',
    ]

from collections import namedtuple
import os

from provisioningserver.config import Config
from provisioningserver.pxe.tftppath import compose_image_path
from provisioningserver.utils import parse_key_value_file


class EphemeralImagesDirectoryNotFound(Exception):
    """The ephemeral images directory cannot be found."""


KernelParametersBase = namedtuple(
    "KernelParametersBase", (
        "arch",  # Machine architecture, e.g. "i386"
        "subarch",  # Machine subarchitecture, e.g. "generic"
        "release",  # Ubuntu release, e.g. "precise"
        "purpose",  # Boot purpose, e.g. "commissioning"
        "hostname",  # Machine hostname, e.g. "coleman"
        "domain",  # Machine domain name, e.g. "example.com"
        "preseed_url",  # URL from which a preseed can be obtained.
        "log_host",  # Host/IP to which syslog can be streamed.
        "fs_host",  # Host/IP on which ephemeral filesystems are hosted.
        ))


class KernelParameters(KernelParametersBase):

    # foo._replace() is just ugly, so alias it to __call__.
    __call__ = KernelParametersBase._replace


def compose_initrd_opt(arch, subarch, release, purpose):
    path = "%s/initrd.gz" % compose_image_path(arch, subarch, release, purpose)
    return "initrd=%s" % path


def compose_preseed_opt(preseed_url):
    """Compose a kernel option for preseed URL.

    :param preseed_url: The URL from which a preseed can be fetched.
    """
    return "auto url=%s" % preseed_url


def compose_suite_opt(release):
    return "suite=%s" % release


def compose_hostname_opt(hostname):
    return "hostname=%s" % hostname


def compose_domain_opt(domain):
    return "domain=%s" % domain


def compose_locale_opt():
    locale = 'en_US'
    return "locale=%s" % locale


def compose_logging_opts(log_host):
    return [
        'log_host=%s' % log_host,
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
    config = Config.load_from_cache()
    root = os.path.join(
        config["boot"]["ephemeral"]["directory"],
        release, 'ephemeral', arch)
    try:
        filename = os.path.join(get_last_directory(root), 'info')
    except OSError:
        raise EphemeralImagesDirectoryNotFound(
            "The directory containing the ephemeral images/info is missing "
            "(%r).  Make sure to run the script "
            "'maas-import-pxe-files'." % root)
    name = parse_key_value_file(filename, separator="=")['name']
    return name


def compose_purpose_opts(params):
    """Return the list of the purpose-specific kernel options."""
    if params.purpose == "commissioning":
        return [
            "iscsi_target_name=%s:%s" % (
                ISCSI_TARGET_NAME_PREFIX,
                get_ephemeral_name(params.release, params.arch)),
            "ip=dhcp",
            "ro root=LABEL=cloudimg-rootfs",
            "iscsi_target_ip=%s" % params.fs_host,
            "iscsi_target_port=3260",
            ]
    else:
        return [
            "netcfg/choose_interface=auto"
            ]


def compose_arch_opts(params):
    """Return any architecture-specific options required"""
    if (params.arch, params.subarch) == ("armhf", "highbank"):
        return ["console=ttyAMA0"]
    else:
        return []


def compose_kernel_command_line_new(params):
    """Generate a line of kernel options for booting `node`.

    :type params: `KernelParameters`.
    """
    options = [
        compose_initrd_opt(
            params.arch, params.subarch,
            params.release, params.purpose),
        compose_preseed_opt(params.preseed_url),
        compose_suite_opt(params.release),
        compose_hostname_opt(params.hostname),
        compose_domain_opt(params.domain),
        compose_locale_opt(),
        ]
    options += compose_purpose_opts(params)
    options += compose_logging_opts(params.log_host)
    options += compose_arch_opts(params)
    return ' '.join(options)
