# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate kernel command-line options for inclusion in PXE configs."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_kernel_command_line',
    'KernelParameters',
    ]

from collections import namedtuple
import os

from provisioningserver.config import Config
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
        "extra_opts",  # String of extra options to supply, will be appended
                       # verbatim to the kernel command line
        ))


class KernelParameters(KernelParametersBase):

    # foo._replace() is just ugly, so alias it to __call__.
    __call__ = KernelParametersBase._replace


def compose_preseed_opt(preseed_url):
    """Compose a kernel option for preseed URL.

    :param preseed_url: The URL from which a preseed can be fetched.
    """
    # See https://help.ubuntu.com/12.04/installation-guide
    #   /i386/preseed-using.html#preseed-auto
    return "auto url=%s" % preseed_url


def compose_locale_opt():
    locale = 'en_US'
    return "locale=%s" % locale


def compose_logging_opts(log_host):
    return [
        'log_host=%s' % log_host,
        'log_port=%d' % 514,
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


def compose_hostname_opts(params):
    """Return list of hostname/domain options based on `params`.

    The domain is omitted if `params` does not include it.
    """
    options = [
        'hostname=%s' % params.hostname,
        ]
    if params.domain is not None:
        options.append('domain=%s' % params.domain)
    return options


def compose_purpose_opts(params):
    """Return the list of the purpose-specific kernel options."""
    if params.purpose == "commissioning" or params.purpose == "xinstall":
        # These are kernel parameters read by the ephemeral environment.
        tname = "%s:%s" % (ISCSI_TARGET_NAME_PREFIX,
                           get_ephemeral_name(params.release, params.arch))
        kernel_params = [
            # Read by the open-iscsi initramfs code.
            "iscsi_target_name=%s" % tname,
            "iscsi_target_ip=%s" % params.fs_host,
            "iscsi_target_port=3260",
            "iscsi_initiator=%s" % params.hostname,
            # Read by cloud-initramfs-dyn-netconf and klibc's ipconfig
            # in the initramfs.
            "ip=::::%s:BOOTIF" % params.hostname,
            # kernel / udev name iscsi devices with this path
            "ro root=/dev/disk/by-path/ip-%s:%s-iscsi-%s-lun-1" % (
                params.fs_host, "3260", tname),
            # Read by overlayroot package.
            "overlayroot=tmpfs",
            # Read by cloud-init.
            "cloud-config-url=%s" % params.preseed_url,
            ]
        return kernel_params
    else:
        # These are options used by the Debian Installer.
        return [
            "netcfg/choose_interface=auto",
            # Use the text installer, display only critical messages.
            "text priority=critical",
            compose_preseed_opt(params.preseed_url),
            compose_locale_opt(),
            ] + compose_hostname_opts(params)


def compose_arch_opts(params):
    """Return any architecture-specific options required"""
    if (params.arch, params.subarch) == ("armhf", "highbank"):
        return ["console=ttyAMA0"]
    else:
        # On Intel there are no working sane console= defaults (LP: #1061977)
        return []


def compose_kernel_command_line(params):
    """Generate a line of kernel options for booting `node`.

    :type params: `KernelParameters`.
    """
    options = []
    # nomodeset prevents video mode switching.
    options += ["nomodeset"]
    options += compose_purpose_opts(params)
    # Note: logging opts are not respected by ephemeral images, so
    #       these are actually "purpose_opts" but were left generic
    #       as it would be nice to have.
    options += compose_logging_opts(params.log_host)
    options += compose_arch_opts(params)
    if params.extra_opts:
        options.append(params.extra_opts)
    return ' '.join(options)
