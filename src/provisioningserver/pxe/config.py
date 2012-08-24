# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generating PXE configuration files.

For more about the format of these files:

http://www.syslinux.org/wiki/index.php/SYSLINUX#How_do_I_Configure_SYSLINUX.3F
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'render_pxe_config',
    ]


from errno import ENOENT
from os import path

import posixpath
from provisioningserver.kernel_opts import compose_kernel_command_line_new
from provisioningserver.pxe.tftppath import compose_image_path
import tempita

# TODO: make this configurable.
template_dir = path.dirname(__file__)


def gen_pxe_template_filenames(purpose, arch, subarch):
    """List possible PXE template filenames.

    :param purpose: The boot purpose, e.g. "local".
    :param arch: Main machine architecture.
    :param subarch: Sub-architecture, or "generic" if there is none.
    :param release: The Ubuntu release to be used.

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


def get_pxe_template(purpose, arch, subarch):
    # Templates are loaded each time here so that they can be changed on
    # the fly without restarting the provisioning server.
    for filename in gen_pxe_template_filenames(purpose, arch, subarch):
        try:
            return tempita.Template.from_filename(
                path.join(template_dir, filename), encoding="UTF-8")
        except IOError as error:
            if error.errno != ENOENT:
                raise
    else:
        raise AssertionError(
            "No PXE template found in %r!" % template_dir)


def render_pxe_config(bootpath, kernel_params, **extra):
    """Render a PXE configuration file as a unicode string.

    :param bootpath: The directory path of `pxelinux.0`.
    :param kernel_params: An instance of `KernelParameters`.
    :param extra: Allow for other arguments. This is a safety valve;
        parameters generated in another component (for example, see
        `TFTPBackend.get_config_reader`) won't cause this to break.
    """
    template = get_pxe_template(
        kernel_params.purpose, kernel_params.arch,
        kernel_params.subarch)

    # The locations of the kernel image and the initrd are defined by
    # update_install_files(), in scripts/maas-import-pxe-files.

    def image_dir(params):
        return compose_image_path(
            params.arch, params.subarch,
            params.release, params.purpose)

    def initrd(params):
        return "%s/initrd.gz" % image_dir(params)

    def kernel(params):
        return "%s/linux" % image_dir(params)

    def kernel_command(params):
        return compose_kernel_command_line_new(params)

    def relative(path):
        # Return `path` relative to `bootpath`.
        return posixpath.relpath(path, start=bootpath)

    namespace = {
        "initrd_path": initrd,
        "kernel_command": kernel_command,
        "kernel_params": kernel_params,
        "kernel_path": kernel,
        "relative": relative,
        }
    return template.substitute(namespace)
