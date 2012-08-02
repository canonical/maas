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


from functools import partial
from os import path

import posixpath
from provisioningserver.pxe.tftppath import compose_image_path
import tempita


template_dir = path.dirname(__file__)
template_filename = path.join(template_dir, "config.template")
template = tempita.Template.from_filename(template_filename, encoding="UTF-8")


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
