# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the osystems helpers relating to listing OSes.

This is TEMPORARY: these test cases will be moved into a different
module in a later branch. This is here to avoid conflicts.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import Iterable

from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.rpc import osystems as osystems_module
from provisioningserver.rpc.osystems import (
    gen_operating_system_releases,
    gen_operating_systems,
    )
from provisioningserver.rpc.testing.doubles import StubOS


class TestListOperatingSystemHelpers(MAASTestCase):

    def test_gen_operating_systems_returns_dicts_for_registered_oses(self):
        # Patch in some operating systems with some randomised data. See
        # StubOS for details of the rules that are used to populate the
        # non-random elements.
        os1 = StubOS("kermit", [
            ("statler", "Statler"),
            ("waldorf", "Waldorf"),
        ])
        os2 = StubOS("fozzie", [
            ("swedish-chef", "Swedish-Chef"),
            ("beaker", "Beaker"),
        ])
        self.patch(
            osystems_module, "OperatingSystemRegistry",
            [(os1.name, os1), (os2.name, os2)])
        # The `releases` field in the dict returned is populated by
        # gen_operating_system_releases. That's not under test, so we
        # mock it.
        gen_operating_system_releases = self.patch(
            osystems_module, "gen_operating_system_releases")
        gen_operating_system_releases.return_value = sentinel.releases
        # The operating systems are yielded in name order.
        expected = [
            {
                "name": "fozzie",
                "title": "Fozzie",
                "releases": sentinel.releases,
                "default_release": "swedish-chef",
                "default_commissioning_release": "beaker",
            },
            {
                "name": "kermit",
                "title": "Kermit",
                "releases": sentinel.releases,
                "default_release": "statler",
                "default_commissioning_release": "waldorf",
            },
        ]
        observed = gen_operating_systems()
        self.assertIsInstance(observed, Iterable)
        osystems = list(observed)
        self.assertEqual(expected, osystems)

    def test_gen_operating_system_releases_returns_dicts_for_releases(self):
        # Use an operating system with some randomised data. See StubOS
        # for details of the rules that are used to populate the
        # non-random elements.
        osystem = StubOS("fozzie", [
            ("swedish-chef", "I Am The Swedish-Chef"),
            ("beaker", "Beaker The Phreaker"),
        ])
        expected = [
            {
                "name": "swedish-chef",
                "title": "I Am The Swedish-Chef",
                "requires_license_key": False,
                "can_commission": False,
            },
            {
                "name": "beaker",
                "title": "Beaker The Phreaker",
                "requires_license_key": True,
                "can_commission": True,
            },
        ]
        observed = gen_operating_system_releases(osystem)
        self.assertIsInstance(observed, Iterable)
        releases = list(observed)
        self.assertEqual(expected, releases)
