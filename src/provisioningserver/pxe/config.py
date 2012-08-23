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
from functools import partial
from os import path

import posixpath
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


def render_pxe_config(
    arch, subarch, release, purpose, append, bootpath, **extra):
    """Render a PXE configuration file as a unicode string.

    :param arch: Main machine architecture.
    :param subarch: Sub-architecture, or "generic" if there is none.
    :param release: The OS release, e.g. "precise".
    :param purpose: What's the purpose of this boot, e.g. "install".
    :param append: Additional kernel parameters.
    :param bootpath: The directory path of `pxelinux.0`.
    :param extra: Allow for other arguments. This is a safety valve;
        parameters generated in another component (for example, see
        `TFTPBackend.get_config_reader`) won't cause this to break.
    """
    template = get_pxe_template(purpose, arch, subarch)
    image_dir = compose_image_path(arch, subarch, release, purpose)
    # The locations of the kernel image and the initrd are defined by
    # update_install_files(), in scripts/maas-import-pxe-files.
    namespace = {
        "append": append,
        "initrd": "%s/initrd.gz" % image_dir,
        "kernel": "%s/linux" % image_dir,
        "relpath": partial(posixpath.relpath, start=bootpath),
        }
    return template.substitute(namespace)
