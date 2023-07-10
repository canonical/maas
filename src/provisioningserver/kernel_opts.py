# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate kernel command-line options for inclusion in PXE configs."""


from collections import namedtuple
import os

import curtin
from distro_info import UbuntuDistroInfo
from netaddr import IPAddress

from provisioningserver.drivers import ArchitectureRegistry
from provisioningserver.logger import get_maas_logger, LegacyLogger

log = LegacyLogger()
maaslog = get_maas_logger("kernel_opts")


class EphemeralImagesDirectoryNotFound(Exception):
    """The ephemeral images directory cannot be found."""


KernelParametersBase = namedtuple(
    "KernelParametersBase",
    (
        "osystem",  # Operating system, e.g. "ubuntu"
        "arch",  # Machine architecture, e.g. "i386"
        "subarch",  # Machine subarchitecture, e.g. "generic"
        "release",  # OS release, e.g. "precise"
        "kernel",  # The kernel filename
        "initrd",  # The initrd filename
        "boot_dtb",  # The boot_dtb filename
        "label",  # Image label, e.g. "release"
        "purpose",  # Boot purpose, e.g. "commissioning"
        "hostname",  # Machine hostname, e.g. "coleman"
        "domain",  # Machine domain name, e.g. "example.com"
        "preseed_url",  # URL from which a preseed can be obtained.
        "log_host",  # Host/IP to which syslog can be streamed.
        "log_port",  # Port to which syslog can be streamed.
        "fs_host",  # Host/IP on which ephemeral filesystems are hosted.
        "extra_opts",  # String of extra options to supply, will be appended
        # verbatim to the kernel command line
        "http_boot",  # Used to make sure a MAAS 2.3 rack controller uses
        # http_boot.
        "ephemeral_opts",  # Same as 'extra_opts' but used only in the ephemeral OS
    ),
)


class KernelParameters(KernelParametersBase):
    # foo._replace() is just ugly, so alias it to __call__.
    __call__ = KernelParametersBase._replace

    def __new__(cls, *args, **kwargs):
        if "log_port" not in kwargs or not kwargs["log_port"]:
            # Fallback to the default log_port, when an older region
            # controller doesn't provide that value.
            kwargs["log_port"] = 5247
        return super().__new__(cls, *args, **kwargs)


def compose_logging_opts(params):
    return ["log_host=%s" % params.log_host, "log_port=%d" % params.log_port]


def get_last_directory(root):
    """Return the last directory from the directories in the given root.

    This is used to get the most recent ephemeral import directory.
    The ephemeral directories are named after the release date: 20120424,
    20120424, 20120301, etc. so fetching the last one (sorting by name)
    returns the most recent.
    """
    dirs = (os.path.join(root, directory) for directory in os.listdir(root))
    dirs = filter(os.path.isdir, dirs)
    return max(dirs)


def compose_purpose_opts(params):
    """Return the list of the purpose-specific kernel options."""
    kernel_params = [
        "ro",
        "root=squash:http://%s:5248/images/%s/%s/%s/%s/%s/squashfs"
        % (
            (
                "[%s]" % params.fs_host
                if IPAddress(params.fs_host).version == 6
                else params.fs_host
            ),
            params.osystem,
            params.arch,
            params.subarch,
            params.release,
            params.label,
        ),
        # Read by cloud-initramfs-dyn-netconf initramfs-tools networking
        # configuration in the initramfs.  Choose IPv4 or IPv6 based on the
        # family of fs_host.  If BOOTIF is set, IPv6 config uses that
        # exclusively.
        (
            "ip=::::%s:BOOTIF" % params.hostname
            if IPAddress(params.fs_host).version == 4
            else "ip=off"
        ),
        ("ip6=dhcp" if IPAddress(params.fs_host).version == 6 else "ip6=off"),
        # Read by overlayroot package.
        "overlayroot=tmpfs",
        # LP:1533822 - Disable reading overlay data from disk.
        "overlayroot_cfgdisk=disabled",
        # Select the MAAS datasource by default.
        "cc:{'datasource_list': ['MAAS']}end_cc",
        # Read by cloud-init.
        "cloud-config-url=%s" % params.preseed_url,
    ]
    return kernel_params


def compose_apparmor_opts(params):
    if params.osystem == "ubuntu":
        di = UbuntuDistroInfo()
        codenames = di.get_all()
        if params.release in codenames and (
            codenames.index(params.release) < codenames.index("jammy")
        ):
            # Disable apparmor in the ephemeral environment. This addresses
            # MAAS bug LP: #1677336 due to LP: #1408106
            return ["apparmor=0"]
    return []


def compose_arch_opts(params):
    """Return any architecture-specific options required"""
    arch_subarch = f"{params.arch}/{params.subarch}"
    resource = ArchitectureRegistry.get_item(arch_subarch)
    if resource is not None and resource.kernel_options is not None:
        return resource.kernel_options
    else:
        return []


CURTIN_KERNEL_CMDLINE_NAME = "KERNEL_CMDLINE_COPY_TO_INSTALL_SEP"


def get_curtin_kernel_cmdline_sep():
    """Return the separator for passing extra parameters to the kernel."""
    return getattr(curtin, CURTIN_KERNEL_CMDLINE_NAME, "--")


def compose_kernel_command_line(params):
    """Generate a line of kernel options for booting `node`.

    :type params: `KernelParameters`.
    """
    options = []
    # nomodeset prevents video mode switching.
    options += ["nomodeset"]
    options += compose_purpose_opts(params)
    options += compose_apparmor_opts(params)
    # Note: logging opts are not respected by ephemeral images, so
    #       these are actually "purpose_opts" but were left generic
    #       as it would be nice to have.
    options += compose_logging_opts(params)
    options += compose_arch_opts(params)
    if params.ephemeral_opts:
        options.append(params.ephemeral_opts)
    cmdline_sep = get_curtin_kernel_cmdline_sep()
    if params.extra_opts:
        # Using --- before extra opts makes both d-i and Curtin install
        # them into the grub config when installing an OS, thus causing
        # the options to "stick" when local booting later.
        # see LP: #1402042 for info on '---' versus '--'
        options.append(cmdline_sep)
        options.append(params.extra_opts)
    kernel_opts = " ".join(options)
    log.debug(
        '{hostname}: kernel parameters {cmdline} "{opts}"',
        hostname=params.hostname,
        cmdline=cmdline_sep,
        opts=kernel_opts,
    )
    return kernel_opts
