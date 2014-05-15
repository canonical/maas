# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.ppc64el`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from contextlib import contextmanager
import os

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.boot import (
    BootMethodInstallError,
    ppc64el as ppc64el_module,
    utils,
    )
from provisioningserver.boot.ppc64el import (
    GRUB_CONFIG,
    PPC64ELBootMethod,
    )
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters


class TestPPC64ELBootMethod(MAASTestCase):
    """Tests `provisioningserver.boot.ppc64el.PPC64ELBootMethod`."""

    def test_match_config_path_returns_none(self):
        method = PPC64ELBootMethod()
        paths = [factory.getRandomString() for _ in range(3)]
        for path in paths:
            self.assertEqual(None, method.match_config_path(path))

    def test_render_config_returns_empty_string(self):
        method = PPC64ELBootMethod()
        params = [make_kernel_parameters() for _ in range(3)]
        for param in params:
            self.assertEqual("", method.render_config(params))

    def test_install_bootloader_get_package_raises_error(self):
        method = PPC64ELBootMethod()
        self.patch(utils, 'get_updates_package').return_value = (None, None)
        self.assertRaises(
            BootMethodInstallError, method.install_bootloader, None)

    def test_install_bootloader(self):
        method = PPC64ELBootMethod()
        filename = factory.make_name('dpkg')
        data = factory.getRandomString()
        tmp = self.make_dir()
        dest = self.make_dir()

        @contextmanager
        def tempdir():
            try:
                yield tmp
            finally:
                pass

        mock_get_updates_package = self.patch(utils, 'get_updates_package')
        mock_get_updates_package.return_value = (data, filename)
        self.patch(ppc64el_module, 'call_and_check')
        self.patch(ppc64el_module, 'tempdir').side_effect = tempdir

        mock_install_bootloader = self.patch(
            ppc64el_module, 'install_bootloader')

        method.install_bootloader(dest)

        with open(os.path.join(tmp, filename), 'rb') as stream:
            saved_data = stream.read()
        self.assertEqual(data, saved_data)

        with open(os.path.join(tmp, 'grub.cfg'), 'rb') as stream:
            saved_config = stream.read().decode('utf-8')
        self.assertEqual(GRUB_CONFIG, saved_config)

        mkimage_expected = os.path.join(tmp, method.bootloader_path)
        dest_expected = os.path.join(dest, method.bootloader_path)
        self.assertThat(
            mock_install_bootloader,
            MockCalledOnceWith(mkimage_expected, dest_expected))
