# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Domain forms."""

import random

from maasserver.forms.domain import DomainForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks, reload_object


class TestDomainForm(MAASServerTestCase):
    def test_creates_domain(self):
        domain_name = factory.make_name("domain")
        domain_authoritative = factory.pick_bool()
        ttl = random.randint(1, 604800)
        form = DomainForm(
            {
                "name": domain_name,
                "authoritative": domain_authoritative,
                "ttl": ttl,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            domain = form.save()

        self.assertEqual(domain_name, domain.name)
        self.assertEqual(domain_authoritative, domain.authoritative)
        self.assertEqual(ttl, domain.ttl)

    def test_doest_require_name_on_update(self):
        domain = factory.make_Domain()
        form = DomainForm(instance=domain, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_domain(self):
        new_name = factory.make_name("domain")
        old_authoritative = factory.pick_bool()
        domain = factory.make_Domain(authoritative=old_authoritative)
        new_authoritative = not old_authoritative
        new_ttl = random.randint(1, 604800)

        form = DomainForm(
            instance=domain,
            data={
                "name": new_name,
                "authoritative": new_authoritative,
                "ttl": new_ttl,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            form.save()

        domain = reload_object(domain)
        self.assertEqual(new_name, domain.name)
        self.assertEqual(new_authoritative, domain.authoritative)
        self.assertEqual(new_ttl, domain.ttl)

    def test_accepts_ttl(self):
        name = factory.make_name("domain")
        ttl = random.randint(1, 604800)
        authoritative = factory.pick_bool()
        form = DomainForm(
            {"name": name, "authoritative": authoritative, "ttl": ttl}
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            domain = form.save()

        self.assertEqual(name, domain.name)
        self.assertEqual(authoritative, domain.authoritative)
        self.assertEqual(ttl, domain.ttl)

    def test_accepts_ttl_equals_none(self):
        name = factory.make_name("domain")
        ttl = random.randint(1, 604800)
        authoritative = factory.pick_bool()
        form = DomainForm(
            {"name": name, "authoritative": authoritative, "ttl": ttl}
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            domain = form.save()

        form = DomainForm(instance=domain, data={"ttl": None})
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            domain = form.save()

        self.assertEqual(name, domain.name)
        self.assertEqual(authoritative, domain.authoritative)
        self.assertIsNone(domain.ttl)

    def test_can_create_forward_dns_server(self):
        name = factory.make_name("domain")
        forward_dns_servers = [factory.make_ip_address() for _ in range(0, 2)]
        form = DomainForm(
            {
                "name": name,
                "authoritative": False,
                "forward_dns_servers": "  ".join(forward_dns_servers),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            domain = form.save()

        self.assertEqual(
            forward_dns_servers,
            [
                fwd_dns_srvr.ip_address
                for fwd_dns_srvr in domain.forward_dns_servers
            ],
        )
        for fwd_dns_srvr in domain.forward_dns_servers:
            self.assertEqual(fwd_dns_srvr.port, 53)

    def test_can_create_forward_dns_server_with_port(self):
        name = factory.make_name("domain")
        forward_dns_servers = [
            f"{factory.make_ip_address(ipv6=False)}:5353" for _ in range(0, 2)
        ]
        form = DomainForm(
            {
                "name": name,
                "authoritative": False,
                "forward_dns_servers": "  ".join(forward_dns_servers),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            domain = form.save()

        self.assertEqual(
            forward_dns_servers,
            [
                fwd_dns_srvr.ip_and_port
                for fwd_dns_srvr in domain.forward_dns_servers
            ],
        )

    def test_validate_authority(self):
        name = factory.make_name("domain")
        forward_dns_servers = [factory.make_ip_address() for _ in range(0, 2)]
        form = DomainForm(
            {
                "name": name,
                "authoritative": True,
                "forward_dns_servers": " ".join(forward_dns_servers),
            }
        )
        self.assertRaises(ValueError, form.save)
