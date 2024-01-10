# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Methods."""


from abc import ABCMeta, abstractproperty
from errno import ENOENT
from functools import lru_cache
from io import BytesIO
import os
from typing import Dict

import tempita
from tftp.backend import IReader
from twisted.internet.defer import inlineCallbacks, returnValue
from zope.interface import implementer

from provisioningserver.config import debug_enabled
from provisioningserver.events import EVENT_TYPES, try_send_rack_event
from provisioningserver.kernel_opts import (
    compose_kernel_command_line,
    KernelParameters,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.region import GetArchiveMirrors
from provisioningserver.utils import locate_template, tftp
from provisioningserver.utils.network import (
    convert_host_to_uri_str,
    find_mac_via_arp,
)
from provisioningserver.utils.registry import Registry
from provisioningserver.utils.twisted import asynchronous

maaslog = get_maas_logger("bootloaders")


@asynchronous
def get_archive_mirrors():
    client = getRegionClient()
    return client(GetArchiveMirrors)


@asynchronous(timeout=10)
@inlineCallbacks
def get_main_archive_url():
    mirrors = yield get_archive_mirrors()
    main_url = mirrors["main"].geturl()
    returnValue(main_url)


@asynchronous(timeout=10)
@inlineCallbacks
def get_ports_archive_url():
    mirrors = yield get_archive_mirrors()
    ports_url = mirrors["ports"].geturl()
    returnValue(ports_url)


@implementer(IReader)
class BytesReader:
    def __init__(self, data):
        super().__init__()
        self.buffer = BytesIO(data)
        self.size = len(data)

    def read(self, size):
        return self.buffer.read(size)

    def finish(self):
        self.buffer.close()


class BootMethodError(Exception):
    """Exception raised for errors from a BootMethod."""


def get_parameters(match) -> Dict[str, str]:
    """Helper that gets the matched parameters from the regex match."""
    return {
        key: value.decode("ascii")
        for key, value in match.groupdict().items()
        if value is not None
    }


def gen_template_filenames(purpose, arch, subarch):
    """List possible template filenames.

    :param purpose: The boot purpose, e.g. "local".
    :param arch: Main machine architecture.
    :param subarch: Sub-architecture, or "generic" if there is none.

    Returns a list of possible PXE template filenames using the following
    lookup order:

      config.{purpose}.{arch}.{subarch}.template
      config.{purpose}.{arch}.template
      config.{purpose}.template
      config.template

    """
    elements = [purpose, arch, subarch]
    while len(elements) >= 1:
        yield "config.%s.template" % ".".join(elements)
        elements.pop()
    yield "config.template"


def get_remote_mac():
    """Gets the requestors MAC address from arp cache.

    This is used, when the dhcp lease file is not up-to-date soon enough
    to extract the MAC address from the IP address assigned by dhcp.
    """
    remote_host, remote_port = tftp.get_remote_address()
    return find_mac_via_arp(remote_host)


class BootMethod(metaclass=ABCMeta):
    """Skeleton for a boot method."""

    # Path prefix that is used for the pxelinux.cfg. Used for
    # the dhcpd.conf that is generated.  Format is "path/to/dir/".
    # relative to tftpboot directory.
    path_prefix = None

    # Set to `True` to have the path_prefix to be an absolute prefix
    # for the HTTP boot endpoint. It is not required that `path_prefix`
    # also be set.
    path_prefix_http = False

    # Force that the path_prefix is sent over DHCP even if the client didn't
    # request that information.
    path_prefix_force = False

    # Use the full absolute URL for filename access. Instead of providing a
    # relative path to the `bootloader_path` ensure that the DHCP renders
    # with an absolute path.
    absolute_url_as_filename = False

    # When providing a URL in the bootloader make it HTTP instead of TFTP.
    # Includes "HTTPClient" as the vendor-class-identifier.
    http_url = False

    # Bootloader files to symlink into the root tftp directory.
    bootloader_files = []

    @abstractproperty
    def name(self):
        """Name of the boot method."""

    @abstractproperty
    def bios_boot_method(self):
        """Method used by the bios to boot. E.g. `pxe`."""

    @abstractproperty
    def template_subdir(self):
        """Name of template sub-directory."""

    @abstractproperty
    def bootloader_arches(self):
        """Arches for which this boot method is for."""

    @abstractproperty
    def bootloader_path(self):
        """Relative path from `path_prefix` to boot loader."""

    @abstractproperty
    def arch_octet(self):
        """Architecture type that supports this method. Used for the
        dhcpd.conf file that is generated. Must be in the format XX:XX.
        See http://www.iana.org/assignments/dhcpv6-parameters/
        dhcpv6-parameters.xhtml#processor-architecture
        """

    @abstractproperty
    def user_class(self):
        """User class that supports this method. Used for the
        dhcpd.conf file that is generated."""

    def match_path(self, backend, path):
        """Checks path for a file the boot method needs to handle.

        :param backend: requesting backend
        :param path: requested path
        :return: dict of match params from path, None if no match
        """
        return None

    def get_reader(self, backend, kernel_params, **extra):
        """Gets the reader the backend will use for this combination of
        boot method, kernel parameters, and extra parameters.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """
        return None

    def install_templates(self, destination: str):
        """Installs the required files for this boot method into the
        destination.

        :param destination: path to install bootloader templates
        """

    def __init__(self):
        super().__init__()
        # Check the types of subclasses' properties.
        assert isinstance(self.name, str)
        assert isinstance(self.bios_boot_method, str)
        assert isinstance(self.bootloader_path, str)
        assert isinstance(self.template_subdir, str) or (
            self.template_subdir is None
        )
        assert isinstance(self.bootloader_arches, list) and all(
            isinstance(element, str) for element in self.bootloader_arches
        )
        assert isinstance(self.bootloader_files, list) and all(
            isinstance(element, str) for element in self.bootloader_files
        )
        assert (
            isinstance(self.arch_octet, str)
            or (
                isinstance(self.arch_octet, list)
                and all(
                    isinstance(element, str) for element in self.arch_octet
                )
            )
            or self.arch_octet is None
        )
        assert isinstance(self.user_class, str) or self.user_class is None
        self.get_template_dir = lru_cache(maxsize=1)(self._get_template_dir)
        self.get_template = lru_cache(maxsize=512)(self._get_template)

    def _get_template_dir(self):
        """Gets the template directory for the boot method."""
        return locate_template(f"{self.template_subdir}")

    def _get_template(self, purpose, arch, subarch):
        """Gets the best avaliable template for the boot method.

        Templates are loaded each time here so that they can be changed on
        the fly without restarting the provisioning server.

        :param purpose: The boot purpose, e.g. "local".
        :param arch: Main machine architecture.
        :param subarch: Sub-architecture, or "generic" if there is none.
        :return: `tempita.Template`
        """
        pxe_templates_dir = self.get_template_dir()
        for filename in gen_template_filenames(purpose, arch, subarch):
            template_name = os.path.join(pxe_templates_dir, filename)
            try:
                return tempita.Template.from_filename(
                    template_name, encoding="UTF-8"
                )
            except OSError as error:
                if error.errno != ENOENT:
                    raise
        else:
            error_msg = (
                "No PXE template found in %r for:\n"
                "  Purpose: %r, Arch: %r, Subarch: %r\n"
                "This can happen if you manually power up a node when its "
                "state is not one that allows it. Is the node in the "
                "'New' or 'Ready' states? It needs to be Enlisting, "
                "Commissioning or Allocated."
                % (pxe_templates_dir, purpose, arch, subarch)
            )
            try_send_rack_event(EVENT_TYPES.RACK_IMPORT_ERROR, error_msg)
            raise AssertionError(error_msg)

    def compose_template_namespace(self, kernel_params: KernelParameters):
        """Composes the namespace variables that are used by a boot
        method template.
        """
        dtb_subarchs = ["xgene-uboot-mustang"]

        def fs_host(params: KernelParameters):
            return f"http://{convert_host_to_uri_str(params.fs_host)}:5248/images/"

        def initrd_path(params: KernelParameters):
            return params.initrd or "boot-initrd"

        def kernel_name(params: KernelParameters):
            return kernel_path(params).split("/")[-1]

        def kernel_path(params: KernelParameters):
            return params.kernel or "boot-kernel"

        def dtb_path(params: KernelParameters):
            if params.subarch in dtb_subarchs:
                return params.boot_dtb or "boot-dtb"
            else:
                return None

        def kernel_command(params: KernelParameters):
            return compose_kernel_command_line(params)

        namespace = {
            "fs_host": fs_host,
            "initrd_path": initrd_path,
            "kernel_command": kernel_command,
            "kernel_params": kernel_params,
            "kernel_path": kernel_path,
            "kernel_name": kernel_name,
            "dtb_path": dtb_path,
            "debug": debug_enabled(),
        }

        return namespace


class BootMethodRegistry(Registry):
    """Registry for boot method classes."""


# Import the supported boot methods after defining BootMethod.
from provisioningserver.boot.ipxe import IPXEBootMethod  # noqa:E402 isort:skip
from provisioningserver.boot.grub import (  # noqa:E402 isort:skip
    UEFIAMD64BootMethod,
    UEFIAMD64HTTPBootMethod,
    UEFIEBCBootMethod,
    UEFIARM64BootMethod,
    UEFIARM64HTTPBootMethod,
    OpenFirmwarePPC64ELBootMethod,
)
from provisioningserver.boot.powernv import (  # noqa:E402 isort:skip
    PowerNVBootMethod,
)
from provisioningserver.boot.pxe import PXEBootMethod  # noqa:E402 isort:skip
from provisioningserver.boot.s390x import (  # noqa:E402 isort:skip
    S390XBootMethod,
)
from provisioningserver.boot.s390x_partition import (  # noqa:E402 isort:skip
    S390XPartitionBootMethod,
)
from provisioningserver.boot.windows import (  # noqa:E402 isort:skip
    WindowsPXEBootMethod,
)

builtin_boot_methods = [
    IPXEBootMethod(),
    PXEBootMethod(),
    UEFIAMD64BootMethod(),
    UEFIAMD64HTTPBootMethod(),
    UEFIEBCBootMethod(),
    UEFIARM64BootMethod(),
    UEFIARM64HTTPBootMethod(),
    OpenFirmwarePPC64ELBootMethod(),
    PowerNVBootMethod(),
    WindowsPXEBootMethod(),
    S390XBootMethod(),
    S390XPartitionBootMethod(),
]
for method in builtin_boot_methods:
    BootMethodRegistry.register_item(method.name, method)


def install_boot_method_templates(tftp_root: str):
    os.makedirs(tftp_root, exist_ok=True)
    for _, m in BootMethodRegistry:
        m.install_templates(tftp_root)
