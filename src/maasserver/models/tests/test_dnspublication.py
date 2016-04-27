# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for general DNS models."""

__all__ = []

from datetime import (
    datetime,
    timedelta,
)
from random import randint

from maasserver.models.dnspublication import DNSPublication
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    Equals,
    HasLength,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    Not,
)


class TestDNSPublication(MAASServerTestCase):
    """Test the `DNSPublication` model."""

    def test_create_empty(self):
        pub = DNSPublication()
        pub.save()
        self.assertThat(
            pub, MatchesStructure(
                serial=IsInstance(int),
                created=IsInstance(datetime),
                source=Equals(""),
            ))

    def test_create_with_values(self):
        serial = randint(1, 5000)
        created = datetime.now() - timedelta(minutes=1098)
        source = factory.make_name("source")
        pub = DNSPublication(serial=serial, created=created, source=source)
        pub.save()
        self.assertThat(
            pub, MatchesStructure(
                serial=Equals(serial),
                created=MatchesAll(
                    IsInstance(datetime),
                    # `created` is always set; given values are ignored.
                    Not(Equals(created)),
                    first_only=True,
                ),
                source=Equals(source),
            ))


class TestDNSPublicationManager(MAASServerTestCase):
    """Test `DNSPublicationManager`."""

    def test_get_most_recent_returns_record_with_highest_id(self):
        DNSPublication(serial=3).save()
        DNSPublication(serial=30).save()
        DNSPublication(serial=10).save()
        self.assertThat(
            DNSPublication.objects.get_most_recent(),
            MatchesStructure(serial=Equals(10)))

    def test_get_most_recent_crashes_when_no_publications(self):
        # This is okay because we're going to ensure (using a migration) that
        # there is never less than one publication in the table. If this crash
        # happens we have bigger problems.
        self.assertRaises(IndexError, DNSPublication.objects.get_most_recent)

    def test_collect_garbage_removes_all_but_most_recent_record(self):
        for serial in range(10):
            DNSPublication(serial=serial).save()
        self.assertThat(DNSPublication.objects.all(), HasLength(10))
        DNSPublication.objects.collect_garbage()
        self.assertThat(DNSPublication.objects.all(), HasLength(1))
        self.assertThat(
            DNSPublication.objects.get_most_recent(),
            MatchesStructure(serial=Equals(serial)))
