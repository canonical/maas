# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for general DNS models."""


from datetime import datetime, timedelta
from random import randint

from django.db import connection
from testtools.matchers import (
    Equals,
    HasLength,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    Not,
)

from maasserver.models.dnspublication import DNSPublication, zone_serial
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestZoneSerial(MAASServerTestCase):
    """Tests for the `maasserver_zone_serial_seq` sequence."""

    def test_parameters(self):
        self.assertThat(
            zone_serial,
            MatchesStructure.byEquality(
                maxvalue=2**32 - 1,
                minvalue=1,
                increment=1,
                cycle=True,
                owner="maasserver_dnspublication.serial",
            ),
        )

    def test_parameters_in_database(self):
        zone_serial.create_if_not_exists()
        query = "SELECT last_value, is_called FROM %s" % zone_serial.name
        with connection.cursor() as cursor:
            cursor.execute(query)
            last_value1, is_called1 = cursor.fetchone()
            next(zone_serial)
            cursor.execute(query)
            last_value2, is_called2 = cursor.fetchone()
            self.assertEqual(1, last_value2 - last_value1)
            self.assertTrue(is_called1)
            self.assertTrue(is_called2)


class TestDNSPublication(MAASServerTestCase):
    """Test the `DNSPublication` model."""

    def test_create_empty(self):
        pub = DNSPublication()
        pub.save()
        self.assertThat(
            pub,
            MatchesStructure(
                serial=IsInstance(int),
                created=IsInstance(datetime),
                source=Equals(""),
            ),
        )

    def test_create_with_values(self):
        serial = randint(1, 5000)
        created = datetime.now() - timedelta(minutes=1098)
        source = factory.make_name("source")
        pub = DNSPublication(serial=serial, created=created, source=source)
        pub.save()
        self.assertThat(
            pub,
            MatchesStructure(
                serial=Equals(serial),
                created=MatchesAll(
                    IsInstance(datetime),
                    # `created` is always set; given values are ignored.
                    Not(Equals(created)),
                    first_only=True,
                ),
                source=Equals(source),
            ),
        )


class TestDNSPublicationManager(MAASServerTestCase):
    """Test `DNSPublicationManager`."""

    def setUp(self):
        super().setUp()
        # These tests expect the DNSPublication table to be empty.
        DNSPublication.objects.all().delete()

    def test_get_most_recent_returns_record_with_highest_id(self):
        DNSPublication(serial=3).save()
        DNSPublication(serial=30).save()
        DNSPublication(serial=10).save()
        self.assertThat(
            DNSPublication.objects.get_most_recent(),
            MatchesStructure(serial=Equals(10)),
        )

    def test_get_most_recent_crashes_when_no_publications(self):
        # This is okay because we ensure (using a migration) that there is
        # never less than one publication in the table. If this crash happens
        # we have bigger problems. However, we do not currently use migrations
        # in tests, so it is important to have a deterministic outcome when
        # there are no publications.
        self.assertRaises(
            DNSPublication.DoesNotExist, DNSPublication.objects.get_most_recent
        )

    def test_collect_garbage_removes_all_but_most_recent_record(self):
        for serial in range(10):
            DNSPublication(serial=serial).save()
        self.assertThat(DNSPublication.objects.all(), HasLength(10))
        DNSPublication.objects.collect_garbage()
        self.assertThat(DNSPublication.objects.all(), HasLength(1))
        self.assertThat(
            DNSPublication.objects.get_most_recent(),
            MatchesStructure(serial=Equals(serial)),
        )

    def test_collect_garbage_does_nothing_when_no_publications(self):
        self.assertThat(DNSPublication.objects.all(), HasLength(0))
        DNSPublication.objects.collect_garbage()
        self.assertThat(DNSPublication.objects.all(), HasLength(0))

    def test_collect_garbage_leaves_records_older_than_specified(self):
        publications = {
            timedelta(days=1): DNSPublication(source="1 day ago"),
            timedelta(minutes=1): DNSPublication(source="1 minute ago"),
            timedelta(seconds=0): DNSPublication(source="now"),
        }

        with connection.cursor() as cursor:
            cursor.execute("SELECT now()")
            [now] = cursor.fetchone()

        # Work from oldest to youngest so that the youngest gets the highest
        # primary key; the primary key is used to determine the most recent.
        for delta in sorted(publications, reverse=True):
            publication = publications[delta]
            publication.save()
            # Use SQL to set `created`; Django's field validation prevents it.
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE maasserver_dnspublication SET created = %s"
                    " WHERE id = %s",
                    [now - delta, publication.id],
                )

        def get_ages():
            pubs = DNSPublication.objects.all()
            return {now - pub.created for pub in pubs}

        deltas = set(publications)
        self.assertThat(get_ages(), Equals(deltas))

        one_second = timedelta(seconds=1)
        # Work from oldest to youngest again, collecting garbage each time.
        while len(deltas) > 1:
            delta = max(deltas)
            # Publications of exactly the specified age are not deleted.
            DNSPublication.objects.collect_garbage(now - delta)
            self.assertThat(get_ages(), Equals(deltas))
            # Publications of just a second over are deleted.
            DNSPublication.objects.collect_garbage(now - delta + one_second)
            self.assertThat(get_ages(), Equals(deltas - {delta}))
            # We're done with this one.
            deltas.discard(delta)

        # The most recent publication will never be deleted.
        DNSPublication.objects.collect_garbage()
        self.assertThat(get_ages(), Equals(deltas))
        self.assertThat(deltas, HasLength(1))
