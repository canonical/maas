# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Methods."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "BootMethod",
    "BootMethodRegistry",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )
from errno import ENOENT
from os import path

from provisioningserver.boot.tftppath import compose_image_path
from provisioningserver.kernel_opts import compose_kernel_command_line
from provisioningserver.utils import locate_config
from provisioningserver.utils.registry import Registry
import tempita


class BootMethodError(Exception):
    """Exception raised for errors from a BootMethod."""


class BootMethodInstallError(BootMethodError):
    """Exception raised for errors from a BootMethod performing
    install_bootloader.
    """


def get_parameters(match):
    """Helper that gets the matched parameters from the
    regex match.
    """
    return {
        key: value
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


class BootMethod:
    """Skeleton for a boot method."""

    __metaclass__ = ABCMeta

    @abstractproperty
    def name(self):
        """Name of the boot method."""

    @abstractproperty
    def template_subdir(self):
        """Name of template sub-directory."""

    @abstractproperty
    def bootloader_path(self):
        """Relative path from tftproot to boot loader."""

    @abstractproperty
    def arch_octet(self):
        """Architecture type that supports this method. Used for the
        dhcpd.conf file that is generated. Must be in the format XX:XX.
        """

    @abstractmethod
    def match_config_path(self, path):
        """Checks path for the configuration file that needs to be
        generated.

        :param path: requested path
        :returns: dict of match params from path, None if no match
        """

    @abstractmethod
    def render_config(self, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_config_reader`) won't cause this to break.
        """

    @abstractmethod
    def install_bootloader(self, destination):
        """Installs the required files for this boot method into the
        destination.

        :param destination: path to install bootloader
        """

    def get_template_dir(self):
        """Gets the template directory for the boot method."""
        return locate_config("templates/%s" % self.template_subdir)

    def get_template(self, purpose, arch, subarch):
        """Gets the best avaliable template for the boot method.

        Templates are loaded each time here so that they can be changed on
        the fly without restarting the provisioning server.

        :param purpose: The boot purpose, e.g. "local".
        :param arch: Main machine architecture.
        :param subarch: Sub-architecture, or "generic" if there is none.
        :returns: `tempita.Template`
        """
        pxe_templates_dir = self.get_template_dir()
        for filename in gen_template_filenames(purpose, arch, subarch):
            template_name = path.join(pxe_templates_dir, filename)
            try:
                return tempita.Template.from_filename(
                    template_name, encoding="UTF-8")
            except IOError as error:
                if error.errno != ENOENT:
                    raise
        else:
            error = (
                "No PXE template found in %r for:\n"
                "  Purpose: %r, Arch: %r, Subarch: %r\n"
                "This can happen if you manually power up a node when its "
                "state is not one that allows it. Is the node in the "
                "'Declared' or 'Ready' states? It needs to be Enlisting, "
                "Commissioning or Allocated." % (
                    pxe_templates_dir, purpose, arch, subarch))

            raise AssertionError(error)

    def compose_template_namespace(self, kernel_params):
        """Composes the namespace variables that are used by a boot
        method template.
        """
        def image_dir(params):
            return compose_image_path(
                'ubuntu', params.arch, params.subarch,
                params.release, params.label)

        def initrd_path(params):
            if params.purpose == "install":
                return "%s/di-initrd" % image_dir(params)
            else:
                return "%s/boot-initrd" % image_dir(params)

        def kernel_path(params):
            if params.purpose == "install":
                return "%s/di-kernel" % image_dir(params)
            else:
                return "%s/boot-kernel" % image_dir(params)

        def kernel_command(params):
            return compose_kernel_command_line(params)

        namespace = {
            "initrd_path": initrd_path,
            "kernel_command": kernel_command,
            "kernel_params": kernel_params,
            "kernel_path": kernel_path,
            }
        return namespace


class BootMethodRegistry(Registry):
    """Registry for boot method classes."""


# Import the supported boot methods after defining BootMethod.
from provisioningserver.boot.pxe import PXEBootMethod
from provisioningserver.boot.uefi import UEFIBootMethod


builtin_boot_methods = [
    PXEBootMethod(),
    UEFIBootMethod(),
]
for method in builtin_boot_methods:
    BootMethodRegistry.register_item(method.name, method)
