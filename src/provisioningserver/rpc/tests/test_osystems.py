# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.osystems`."""


from collections.abc import Iterable
import random
from unittest.mock import sentinel

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystemRegistry,
)
from provisioningserver.rpc import exceptions, osystems
from provisioningserver.rpc.testing.doubles import StubOS
from provisioningserver.testing.os import make_osystem


class TestListOperatingSystemHelpers(MAASTestCase):
    def test_gen_operating_systems_returns_dicts_for_registered_oses(self):
        # Patch in some operating systems with some randomised data. See
        # StubOS for details of the rules that are used to populate the
        # non-random elements.
        os1 = StubOS(
            "kermit", [("statler", "Statler"), ("waldorf", "Waldorf")]
        )
        os2 = StubOS(
            "fozzie", [("swedish-chef", "Swedish-Chef"), ("beaker", "Beaker")]
        )
        self.patch(
            osystems,
            "OperatingSystemRegistry",
            [(os1.name, os1), (os2.name, os2)],
        )
        # The `releases` field in the dict returned is populated by
        # gen_operating_system_releases. That's not under test, so we
        # mock it.
        gen_operating_system_releases = self.patch(
            osystems, "gen_operating_system_releases"
        )
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
        observed = osystems.gen_operating_systems()
        self.assertIsInstance(observed, Iterable)
        self.assertEqual(expected, list(observed))

    def test_gen_operating_system_releases_returns_dicts_for_releases(self):
        # Use an operating system with some randomised data. See StubOS
        # for details of the rules that are used to populate the
        # non-random elements.
        osystem = StubOS(
            "fozzie",
            [
                ("swedish-chef", "I Am The Swedish-Chef"),
                ("beaker", "Beaker The Phreaker"),
            ],
        )
        expected = [
            {
                "name": "beaker",
                "title": "Beaker The Phreaker",
                "requires_license_key": True,
                "can_commission": True,
            },
            {
                "name": "swedish-chef",
                "title": "I Am The Swedish-Chef",
                "requires_license_key": False,
                "can_commission": False,
            },
        ]
        observed = osystems.gen_operating_system_releases(osystem)
        self.assertIsInstance(observed, Iterable)
        self.assertEqual(expected, list(observed))

    def test_gen_operating_system_releases_returns_sorted_releases(self):
        # Use an operating system with some randomised data. See StubOS
        # for details of the rules that are used to populate the
        # non-random elements.
        osystem = StubOS(
            "fozzie",
            [
                ("swedish-chef", "I Am The Swedish-Chef"),
                ("beaker", "Beaker The Phreaker"),
            ],
        )
        observed = osystems.gen_operating_system_releases(osystem)
        self.assertEqual(
            ["beaker", "swedish-chef"],
            [release["name"] for release in observed],
        )


class TestGetOSReleaseTitle(MAASTestCase):
    def test_returns_release_title(self):
        os_name = factory.make_name("os")
        title = factory.make_name("title")
        purposes = [BOOT_IMAGE_PURPOSE.XINSTALL]
        osystem = make_osystem(self, os_name, purposes)
        release = random.choice(osystem.get_supported_releases())
        self.patch(osystem, "get_release_title").return_value = title
        self.assertEqual(
            title, osystems.get_os_release_title(osystem.name, release)
        )

    def test_returns_empty_release_title_when_None_returned(self):
        os_name = factory.make_name("os")
        purposes = [BOOT_IMAGE_PURPOSE.XINSTALL]
        osystem = make_osystem(self, os_name, purposes)
        release = random.choice(osystem.get_supported_releases())
        self.patch(osystem, "get_release_title").return_value = None
        self.assertEqual(
            "", osystems.get_os_release_title(osystem.name, release)
        )

    def test_throws_exception_when_os_does_not_exist(self):
        self.assertRaises(
            exceptions.NoSuchOperatingSystem,
            osystems.get_os_release_title,
            factory.make_name("no-such-os"),
            factory.make_name("bogus-release"),
        )


class TestValidateLicenseKeyErrors(MAASTestCase):
    def test_throws_exception_when_os_does_not_exist(self):
        self.assertRaises(
            exceptions.NoSuchOperatingSystem,
            osystems.validate_license_key,
            factory.make_name("no-such-os"),
            factory.make_name("bogus-release"),
            factory.make_name("key-to-not-much"),
        )


class TestValidateLicenseKey(MAASTestCase):
    def test_validates_key(self):
        os_name = factory.make_name("os")
        purposes = [BOOT_IMAGE_PURPOSE.XINSTALL]
        osystem = make_osystem(self, os_name, purposes)
        release = random.choice(osystem.get_supported_releases())
        os_specific_validate_license_key = self.patch(
            osystem, "validate_license_key"
        )
        osystems.validate_license_key(osystem.name, release, sentinel.key)
        self.assertThat(
            os_specific_validate_license_key,
            MockCalledOnceWith(release, sentinel.key),
        )


class TestGetPreseedDataErrors(MAASTestCase):
    def test_throws_exception_when_os_does_not_exist(self):
        self.assertRaises(
            exceptions.NoSuchOperatingSystem,
            osystems.get_preseed_data,
            factory.make_name("no-such-os"),
            sentinel.preseed_type,
            sentinel.node_system_id,
            sentinel.node_hostname,
            sentinel.consumer_key,
            sentinel.token_key,
            sentinel.token_secret,
            sentinel.metadata_url,
        )


class TestGetPreseedData(MAASTestCase):
    # Check for every OS.
    scenarios = [
        (osystem.name, {"osystem": osystem})
        for _, osystem in OperatingSystemRegistry
    ]

    def test_get_preseed_data_calls_compose_preseed(self):
        # get_preseed_data() calls compose_preseed() on the
        # OperatingSystem instances.
        os_specific_compose_preseed = self.patch(
            self.osystem, "compose_preseed"
        )
        metadata_url = factory.make_parsed_url()
        osystems.get_preseed_data(
            self.osystem.name,
            sentinel.preseed_type,
            sentinel.node_system_id,
            sentinel.node_hostname,
            sentinel.consumer_key,
            sentinel.token_key,
            sentinel.token_secret,
            metadata_url,
        )
        self.assertThat(
            os_specific_compose_preseed,
            MockCalledOnceWith(
                sentinel.preseed_type,
                (sentinel.node_system_id, sentinel.node_hostname),
                (
                    sentinel.consumer_key,
                    sentinel.token_key,
                    sentinel.token_secret,
                ),
                metadata_url.geturl(),
            ),
        )
