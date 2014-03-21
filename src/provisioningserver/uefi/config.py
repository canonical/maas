# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generating UEFI configuration files.

For more about the format of these files:

http://www.gnu.org/software/grub/manual/grub.html#Configuration
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'render_uefi_config',
    ]


from errno import ENOENT
from os import path

from provisioningserver.kernel_opts import compose_kernel_command_line
from provisioningserver.pxe.config import gen_pxe_template_filenames
from provisioningserver.pxe.tftppath import compose_image_path
from provisioningserver.utils import locate_config
import tempita

# Location of UEFI templates, relative to the configuration directory.
TEMPLATES_DIR = 'templates/uefi'


def get_uefi_template(purpose, arch, subarch):
    uefi_templates_dir = locate_config(TEMPLATES_DIR)
    # Templates are loaded each time here so that they can be changed on
    # the fly without restarting the provisioning server.
    for filename in gen_pxe_template_filenames(purpose, arch, subarch):
        template_name = path.join(uefi_templates_dir, filename)
        try:
            return tempita.Template.from_filename(
                template_name, encoding="UTF-8")
        except IOError as error:
            if error.errno != ENOENT:
                raise
    else:
        error = (
            "No UEFI template found in %r for:\n"
            "  Purpose: %r, Arch: %r, Subarch: %r\n"
            "This can happen if you manually power up a node when its "
            "state is not one that allows it. Is the node in the 'Declared' "
            "or 'Ready' states? It needs to be Enlisting, Commissioning or "
            "Allocated." % (
                uefi_templates_dir, purpose, arch, subarch))

        raise AssertionError(error)


def render_uefi_config(kernel_params, **extra):
    """Render a UEFI configuration file as a unicode string.

    :param kernel_params: An instance of `KernelParameters`.
    :param extra: Allow for other arguments. This is a safety valve;
        parameters generated in another component (for example, see
        `TFTPBackend.get_config_reader`) won't cause this to break.
    """
    template = get_uefi_template(
        kernel_params.purpose, kernel_params.arch,
        kernel_params.subarch)

    # The locations of the kernel image and the initrd are defined by
    # update_install_files(), in scripts/maas-import-pxe-files.

    def image_dir(params):
        return compose_image_path(
            params.arch, params.subarch,
            params.release, params.label, params.purpose)

    def initrd_path(params):
        return "%s/initrd.gz" % image_dir(params)

    def kernel_path(params):
        return "%s/linux" % image_dir(params)

    def kernel_command(params):
        return compose_kernel_command_line(params)

    namespace = {
        "initrd_path": initrd_path,
        "kernel_command": kernel_command,
        "kernel_params": kernel_params,
        "kernel_path": kernel_path,
        }
    return template.substitute(namespace)
