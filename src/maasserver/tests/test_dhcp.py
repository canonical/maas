# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP management."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.dhcp import is_dhcp_management_enabled
from maasserver.testing import (
    disable_dhcp_management,
    enable_dhcp_management,
    )
from maasserver.testing.testcase import TestCase


class TestDHCPManagement(TestCase):

    def test_is_dhcp_management_enabled_defaults_to_False(self):
        self.assertFalse(is_dhcp_management_enabled())

    def test_is_dhcp_management_enabled_dns_dhcp_management_True(self):
        enable_dhcp_management()
        self.assertTrue(is_dhcp_management_enabled())

    def test_is_dhcp_management_enabled_dns_dhcp_management_False(self):
        disable_dhcp_management()
        self.assertFalse(is_dhcp_management_enabled())
