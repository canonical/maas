# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the RDNS model."""


from datetime import datetime, timedelta

from django.core.exceptions import ValidationError

from maasserver.models import RDNS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.twisted import TwistedLoggerFixture


class TestRDNSModel(MAASServerTestCase):
    def test_accepts_invalid_hostname(self):
        rdns = factory.make_RDNS(hostname="Game room")
        # Expect no exception. We don't trust reverse DNS to always return
        # something that is valid.
        self.assertEqual("Game room", rdns.hostname)


class TestRDNSManager(MAASServerTestCase):
    def test_get_current_entry__returns_entry(self):
        region = factory.make_RegionController()
        rdns = factory.make_RDNS(ip="10.0.0.1", hostname="test.maas")
        result = RDNS.objects.get_current_entry("10.0.0.1", region)
        self.assertEqual(result.hostname, rdns.hostname)

    def test_get_current_entry__returns_none_if_not_found(self):
        region = factory.make_RegionController()
        result = RDNS.objects.get_current_entry("10.0.0.1", region)
        self.assertIsNone(result)

    def test_allows_separate_observations_per_region(self):
        r1 = factory.make_RegionController()
        r2 = factory.make_RegionController()
        rdns1 = factory.make_RDNS("10.0.0.1", "test.maasr1", r1)
        rdns2 = factory.make_RDNS("10.0.0.1", "test.maasr2", r2)
        result1 = RDNS.objects.get_current_entry("10.0.0.1", r1)
        result2 = RDNS.objects.get_current_entry("10.0.0.1", r2)
        self.assertEqual(result1.id, rdns1.id)
        self.assertEqual(result2.id, rdns2.id)
        self.assertNotEqual(rdns2.id, rdns1.id)

    def test_forbids_duplicate_observation_on_single_region(self):
        region = factory.make_RegionController()
        factory.make_RDNS("10.0.0.1", "test.maas", region)
        with self.assertRaisesRegex(ValidationError, "already exists"):
            factory.make_RDNS("10.0.0.1", "test.maasr2", region)

    def test_set_current_entry_creates_new_with_log(self):
        region = factory.make_RegionController()
        hostname = factory.make_hostname()
        ip = factory.make_ip_address()
        with TwistedLoggerFixture() as logger:
            RDNS.objects.set_current_entry(ip, [hostname], region)
        result = RDNS.objects.first()
        self.assertEqual(ip, result.ip)
        self.assertEqual(hostname, result.hostname)
        self.assertEqual([hostname], result.hostnames)
        self.assertEqual(
            logger.output,
            f"New reverse DNS entry: '{ip}' resolves to '{hostname}'.",
        )

    def test_set_current_entry_updates_existing_hostname_with_log(self):
        region = factory.make_RegionController()
        hostname = factory.make_hostname()
        ip = factory.make_ip_address()
        # Place a random hostname in the record at first...
        factory.make_RDNS(ip, factory.make_hostname(), region)
        # Then expect this function replaces it.
        with TwistedLoggerFixture() as logger:
            RDNS.objects.set_current_entry(ip, [hostname], region)
        result = RDNS.objects.first()
        self.assertEqual(ip, result.ip)
        self.assertEqual(hostname, result.hostname)
        self.assertEqual(
            logger.output,
            f"Reverse DNS entry updated: '{ip}' resolves to '{hostname}'.",
        )

    def test_set_current_entry_updates_existing_hostnames(self):
        region = factory.make_RegionController()
        h1 = factory.make_hostname()
        h2 = factory.make_hostname()
        h3 = factory.make_hostname()
        ip = factory.make_ip_address()
        # Place a random hostname in the record at first...
        factory.make_RDNS(ip, factory.make_hostname(), region)
        # Then expect this function replaces it.
        RDNS.objects.set_current_entry(ip, [h1, h2, h3], region)
        result = RDNS.objects.first()
        self.assertEqual(ip, result.ip)
        self.assertEqual(h1, result.hostname)
        self.assertEqual([h1, h2, h3], result.hostnames)

    def test_set_current_entry_updates_updated_time(self):
        region = factory.make_RegionController()
        hostname = factory.make_hostname()
        ip = factory.make_ip_address()
        yesterday = datetime.now() - timedelta(days=1)
        factory.make_RDNS(ip, hostname, region, updated=yesterday)
        # Nothing changed, so expect that only the last updated time changed.
        RDNS.objects.set_current_entry(ip, [hostname], region)
        result = RDNS.objects.first()
        self.assertGreater(result.updated, yesterday)

    def test_set_current_entry_asserts_for_empty_list(self):
        region = factory.make_RegionController()
        with self.assertRaisesRegex(
            AssertionError, "Results must be non-empty to set RDNS entry"
        ):
            RDNS.objects.set_current_entry(
                factory.make_ip_address(), [], region
            )

    def test_delete_current_entry_ignores_missing_entries(self):
        region = factory.make_RegionController()
        ip = factory.make_ip_address()
        with TwistedLoggerFixture() as logger:
            RDNS.objects.delete_current_entry(ip, region)
        self.assertEqual("", logger.output)

    def test_delete_current_entry_deletes_and_logs_if_entry_deleted(self):
        region = factory.make_RegionController()
        hostname = factory.make_hostname()
        ip = factory.make_ip_address()
        factory.make_RDNS(ip, hostname, region)
        with TwistedLoggerFixture() as logger:
            RDNS.objects.delete_current_entry(ip, region)
        self.assertEqual(
            logger.output,
            f"Deleted reverse DNS entry: '{ip}' (resolved to '{hostname}').",
        )
