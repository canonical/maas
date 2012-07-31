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


from os import path

from provisioningserver.pxe.tftppath import compose_image_path
import tempita


template_dir = path.dirname(__file__)
template_filename = path.join(template_dir, "config.template")
template = tempita.Template.from_filename(template_filename, encoding="UTF-8")


def render_pxe_config(title, arch, subarch, release, purpose, append):
    """Render a PXE configuration file as a unicode string.

    :param title: Title that the node should show on its boot menu.
    :param arch: Main machine architecture.
    :param subarch: Sub-architecture, or "generic" if there is none.
    :param release: The OS release, e.g. "precise".
    :param purpose: What's the purpose of this boot, e.g. "install".
    :param append: Additional kernel parameters.
    """
    image_dir = compose_image_path(arch, subarch, release, purpose)
    return template.substitute(
        title=title, kernel="%s/kernel" % image_dir,
        initrd="%s/initrd.gz" % image_dir, append=append)
