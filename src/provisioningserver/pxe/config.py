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

import tempita


template_dir = path.dirname(__file__)
template_filename = path.join(template_dir, "config.template")
template = tempita.Template.from_filename(template_filename, encoding="UTF-8")


def render_pxe_config(title, kernel, initrd, append):
    """Render a PXE configuration file as a unicode string.

    :param title: Title that the node should show on its boot menu.
    :param kernel: TFTP path to the kernel image to boot.
    :param initrd: TFTP path to the initrd file to boot from.
    :param append: Additional kernel parameters.
    """
    return template.substitute(
        title=title, kernel=kernel, initrd=initrd, append=append)
