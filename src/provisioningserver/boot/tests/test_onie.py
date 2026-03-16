#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the ONIE boot method."""

from maastesting.testcase import MAASTestCase
from provisioningserver.boot import BootMethodRegistry


class TestONIEBootMethod(MAASTestCase):
    """Tests for the ONIE boot method properties."""

    def test_name(self):
        method = self._get_onie_method()
        self.assertEqual("onie", method.name)

    def test_bios_boot_method(self):
        method = self._get_onie_method()
        self.assertEqual("onie", method.bios_boot_method)

    def test_bootloader_path(self):
        method = self._get_onie_method()
        self.assertEqual("MAAS/a/v3/nos-installer", method.bootloader_path)

    def test_template_subdir(self):
        method = self._get_onie_method()
        self.assertEqual("onie", method.template_subdir)

    def test_arch_octet(self):
        method = self._get_onie_method()
        self.assertIsNone(method.arch_octet)

    def test_user_class(self):
        """ONIE should use 'onie_dhcp_user_class' as its user class."""
        method = self._get_onie_method()
        self.assertEqual("onie_dhcp_user_class", method.user_class)

    def test_bootloader_arches(self):
        method = self._get_onie_method()
        self.assertEqual([], method.bootloader_arches)

    def test_path_prefix_http(self):
        method = self._get_onie_method()
        self.assertTrue(method.path_prefix_http)

    def test_absolute_url_as_filename(self):
        method = self._get_onie_method()
        self.assertTrue(method.absolute_url_as_filename)

    def _get_onie_method(self):
        """Get the ONIE boot method from the registry."""
        for name, method in BootMethodRegistry:
            if name == "onie":
                return method
        self.fail("ONIE boot method not found in registry")
