import os
import random
from unittest.mock import patch

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.arch import get_architecture


class TestGetArchitecture(MAASTestCase):
    def tearDown(self):
        super().tearDown()
        get_architecture.cache_clear()

    @patch("apt_pkg.get_architectures")
    def test_get_architecture_from_deb(self, mock_get_architectures):
        arch = random.choice(["i386", "amd64", "arm64", "ppc64el"])
        mock_get_architectures.return_value = [arch, "otherarch"]
        ret_arch = get_architecture()
        self.assertEqual(arch, ret_arch)

    @patch("apt_pkg.get_architectures")
    def test_get_architecture_from_snap_env(self, mock_get_architectures):
        arch = factory.make_name("arch")
        self.patch(os, "environ", {"SNAP_ARCH": arch})
        ret_arch = get_architecture()
        self.assertEqual(arch, ret_arch)
        mock_get_architectures.assert_not_called()
