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

from django.core.management import call_command
from maasserver.enum import ARCHITECTURE_CHOICES
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from provisioningserver.pxe.pxeconfig import PXEConfig
from provisioningserver.pxe.tftppath import (
    compose_config_path,
    compose_image_path,
    locate_tftp_path,
    )
from testtools.matchers import (
    Contains,
    FileContains,
    )


class TestGenerateEnlistmentPXE(TestCase):

    def test_generates_default_pxe_config(self):
        arch = factory.getRandomChoice(ARCHITECTURE_CHOICES)
        subarch = 'generic'
        release = 'precise'
        tftproot = self.make_dir()
        self.patch(PXEConfig, 'target_basedir', tftproot)
        call_command(
            'generate_enlistment_pxe', arch=arch, release=release,
            tftproot=tftproot)
        # This produces a "default" PXE config file in the right place.
        # It refers to the kernel and initrd for the requested
        # architecture and release.
        result_path = locate_tftp_path(
            compose_config_path(arch, subarch, 'default'),
            tftproot=tftproot)
        self.assertThat(
            result_path,
            FileContains(matcher=Contains(
                compose_image_path(arch, subarch, release, 'install') +
                    '/linux')))
