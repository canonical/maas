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
from maasserver.models import Config
from maastesting.testcase import TestCase


class TestDHCPManagement(TestCase):

    def test_is_dhcp_management_enabled_defaults_to_False(self):
        self.assertFalse(is_dhcp_management_enabled())

    def test_is_dhcp_management_enabled_follows_manage_dhcp_config(self):
        Config.objects.set_config('manage_dhcp', True)
        self.assertTrue(is_dhcp_management_enabled())
