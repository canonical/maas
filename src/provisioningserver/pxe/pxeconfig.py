# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PXE configuration file."""

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

from celeryconfig import (
    PXE_TEMPLATES_DIR,
    TFTPROOT,
    )
import tempita


class PXEConfigFail(Exception):
    """Raised if there's a problem with a PXE config."""


class PXEConfig:
    """A PXE configuration file.

    Encapsulation of PXE config templates and parameter substitution.

    :param arch: The architecture of the context node.
    :type arch: string
    :param subarch: The sub-architecture of the context node. This is
        optional because some architectures such as i386 don't have a
        sub-architecture.  If not passed, a directory name of "generic"
        is used in the subarch part of the path to the target file.
    :type subarch: string
    :param mac: If specified will write out a mac-specific pxe file.
        If not specified will write out a "default" file.
        Note: Ensure the mac is passed in a colon-separated format like
        aa:bb:cc:dd:ee:ff.  This is the default for MAC addresses coming
        from the database fields in MAAS, so it's not heavily checked here.
    :type mac: string
    :param tftproot: Base directory to write PXE configurations to,
        e.g.  /var/lib/tftpboot/ (which is also the default).  The config
        file will go into a directory determined by the architecture that
        it's for: `/maas/<target_dir>/<arch>/<subarch>/pxelinux.cfg/`
    :type tftproot: string

    :raises PXEConfigFail: if there's a problem with template parameters
        or the MAC address looks incorrectly formatted.

    Use this class by instantiating with parameters that define its location:

    >>> pxeconfig = PXEConfig("armhf", "armadaxp", mac="00:a1:b2:c3:e4:d5")

    and then write the file with:

    >>> pxeconfig.write_config(
    ...     menutitle="menutitle", kernelimage="/my/kernel",
            append="initrd=blah url=blah")
    """

    def __init__(self, arch, subarch=None, mac=None, tftproot=None):
        if subarch is None:
            subarch = "generic"
        if tftproot is None:
            tftproot = TFTPROOT
        self.target_basedir = os.path.join(tftproot, 'maas')
        self._validate_mac(mac)
        self.template = os.path.join(self.template_basedir, "maas.template")
        self.target_dir = os.path.join(
            self.target_basedir,
            arch,
            subarch,
            "pxelinux.cfg")
        if mac is not None:
            filename = mac.replace(':', '-')
        else:
            filename = "default"
        self.target_file = os.path.join(self.target_dir, filename)

    @property
    def template_basedir(self):
        return PXE_TEMPLATES_DIR

    def _validate_mac(self, mac):
        # A MAC address should be of the form aa:bb:cc:dd:ee:ff with
        # precisely five colons in it.  We do a cursory check since most
        # MACs will come from the DB which are already checked and
        # formatted.
        if mac is None:
            return
        colon_count = mac.count(":")
        if colon_count != 5:
            raise PXEConfigFail(
                "Expecting exactly five ':' chars, found %s" % colon_count)

    def get_template(self):
        with open(self.template, "r") as f:
            return tempita.Template(f.read(), name=self.template)

    def render_template(self, template, **kwargs):
        try:
            return template.substitute(kwargs)
        except NameError as error:
            raise PXEConfigFail(*error.args)

    def write_config(self, **kwargs):
        """Write out this PXE config file.

        :param menutitle: The PXE menu title shown.
        :param kernelimage: The path to the kernel in the TFTP server
        :param append: Kernel parameters to append.

        Any required directories will be created but the caller must have
        permission to make them and write the file.
        """
        template = self.get_template()
        rendered = self.render_template(template, **kwargs)
        if not os.path.isdir(self.target_dir):
            os.makedirs(self.target_dir)
        with open(self.target_file, "w") as f:
            f.write(rendered)
