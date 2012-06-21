# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the generate-enlistment-pxe command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os.path

from django.core.management import call_command
from maasserver.enum import ARCHITECTURE_CHOICES
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from provisioningserver.pxe.pxeconfig import PXEConfig


class TestGenerateEnlistmentPXE(TestCase):

    def test_generates_default_pxe_config(self):
        arch = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        release = 'precise'
        tftpdir = self.make_dir()
        self.patch(PXEConfig, 'target_basedir', tftpdir)
        call_command(
            'generate_enlistment_pxe', arch=arch, release=release,
            pxe_target_dir=tftpdir)
        # This produces a "default" PXE config file in the right place.
        # It refers to the kernel and initrd for the requested
        # architecture and release.
        result_path = os.path.join(
            tftpdir, arch, 'generic', 'pxelinux.cfg', 'default')
        with open(result_path) as result_file:
            contents = result_file.read()
        self.assertIn(
            '/'.join(['/maas', arch, 'generic', release, 'install', 'linux']),
            contents)
