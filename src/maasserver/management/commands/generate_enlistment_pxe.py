# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: generate a PXE configuration file for node enlistment.

Produces the "default" PXE configuration that we provide to nodes that
MAAS is not yet aware of.  A node that netboots using this configuration
will then register itself with the MAAS.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'Command',
    ]


from optparse import make_option

from django.core.management.base import BaseCommand
from provisioningserver.pxe.pxeconfig import PXEConfig


class Command(BaseCommand):
    """Print out enlistment PXE config."""

    option_list = BaseCommand.option_list + (
        make_option(
            '--arch', dest='arch', default=None,
            help="Main system architecture to generate config for."),
        make_option(
            '--subarch', dest='arch', default='generic',
            help="Sub-architecture of the main architecture."),
        make_option(
            '--release', dest='release', default=None,
            help="Ubuntu release to run when enlisting nodes."),
        make_option(
            '--pxe-target-dir', dest='pxe_target_dir', default=None,
            help="Write PXE config here instead of in its normal location."),
        )

    def handle(self, arch=None, subarch='generic', release=None,
               pxe_target_dir=None, **kwargs):
        image_path = '/maas/%s/%s/%s/install' % (arch, subarch, release)
        # TODO: This needs to go somewhere more appropriate, and
        # probably contain more appropriate options.
        kernel_opts = ' '.join([
            # Default kernel options (similar to those used by Cobbler):
            'initrd=%s' % '/'.join([image_path, 'initrd.gz']),
            'ksdevice=bootif',
            'lang=  text ',
            'hostname=%s-%s' % (release, arch),
            'domain=local.lan',
            'suite=%s' % release,

            # MAAS-specific options:
            'priority=critical',
            'local=en_US',
            'netcfg/choose_interface=auto',
            ])
        template_args = {
            'menutitle': "Enlisting with MAAS",
            # Enlistment uses the same kernel as installation.
            'kernelimage': '/'.join([image_path, 'linux']),
            'append': kernel_opts,
        }
        writer = PXEConfig(arch, subarch, pxe_target_dir=pxe_target_dir)
        writer.write_config(**template_args)
