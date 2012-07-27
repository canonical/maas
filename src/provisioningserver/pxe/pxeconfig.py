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
    'PXEConfig',
    'PXEConfigFail',
    ]


import os

from celeryconfig import PXE_TEMPLATES_DIR
import tempita


class PXEConfigFail(Exception):
    """Raised if there's a problem with a PXE config."""


class PXEConfig:
    """A PXE configuration file.

    Encapsulation of PXE config templates and parameter substitution.

    :param arch: The architecture to write a configuration for, e.g. i386.
    :type arch: string
    :param subarch: Sub-architecture.  Only needed for architectures that
        have sub-architectures, such as ARM; other architectures use
        a sub-architecture of "generic" (which is the default).
    :type subarch: string

    :raises PXEConfigFail: if there's a problem substituting the template
        parameters.

    Use this class by instantiating with parameters that define its location:

    >>> pxeconfig = PXEConfig("armhf", "armadaxp")

    and then produce a configuration file with:

    >>> pxeconfig.get_config(
    ...     menu_title="Booting", kernel="/my/kernel", initrd="/my/initrd",
            append="auto url=blah")
    """

    def __init__(self, arch, subarch='generic'):
        self.template = os.path.join(self.template_basedir, "maas.template")

    @property
    def template_basedir(self):
        """Directory where PXE templates are stored."""
        if PXE_TEMPLATES_DIR is None:
            # The PXE templates are installed into the same location as this
            # file, and also live in the same directory as this file in the
            # source tree.
            return os.path.join(os.path.dirname(__file__), 'templates')
        else:
            return PXE_TEMPLATES_DIR

    def get_template(self):
        with open(self.template, "r") as f:
            return tempita.Template(f.read(), name=self.template)

    def render_template(self, template, **kwargs):
        try:
            return template.substitute(kwargs)
        except NameError as error:
            raise PXEConfigFail(*error.args)

    def get_config(self, **kwargs):
        """Return this PXE config file as a unicode string.

        :param menu_title: Title that the node should show on its boot menu.
        :param kernel: TFTP path to the kernel image to boot.
        :param initrd: TFTP path to the initrd file to boot from.
        :param append: Additional parameters to append to the kernel
            command line.
        """
        template = self.get_template()
        return self.render_template(template, **kwargs)
