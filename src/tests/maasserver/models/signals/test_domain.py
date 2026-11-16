# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.models import DNSPublication
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


# NOTE: serial 1 is created by initial migration
class TestPostSaveDomainSignal(MAASServerTestCase):
    def test_save_authoritative_domain_creates_dnspublication(self):
        factory.make_Domain("example.com", authoritative=True)
        # serial 1 is created by initial migration
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual("added zone example.com", dnspublication.source)

    def test_save_non_authoritative_domain_does_not_create_dnspublication(
        self,
    ):
        factory.make_Domain("example.com", authoritative=False)
        self.assertEqual(1, DNSPublication.objects.count())


class TestPostDeleteDomainSignal(MAASServerTestCase):
    def test_delete_authoritative_domain_creates_dnspublication(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        domain.delete()
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual("removed zone example.com", dnspublication.source)

    def test_delete_non_authoritative_domain_does_not_create_dnspublication(
        self,
    ):
        domain = factory.make_Domain("example.com", authoritative=False)
        dnspublication_count_before_delete = DNSPublication.objects.count()
        domain.delete()
        self.assertEqual(
            dnspublication_count_before_delete, DNSPublication.objects.count()
        )


class TestUpdateDomainSignal(MAASServerTestCase):
    def test_domain_turns_authoritative(self):
        domain = factory.make_Domain("example.com", authoritative=False)
        domain.authoritative = True
        domain.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual("added zone example.com", dnspublication.source)

    def test_domain_turns_non_authoritative(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        domain.authoritative = False
        domain.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual("removed zone example.com", dnspublication.source)

    def test_domain_changes_name_and_ttl(self):
        domain = factory.make_Domain(
            "example.com", authoritative=True, ttl=3600
        )
        domain.name = "example.org"
        domain.ttl = 7200
        domain.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertIn(
            "renamed zone from example.com to example.org",
            dnspublication.source,
        )
        self.assertIn("changed TTL from 3600 to 7200", dnspublication.source)
