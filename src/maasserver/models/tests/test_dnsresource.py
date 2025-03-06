# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import re

from django.core.exceptions import PermissionDenied, ValidationError

from maasserver.enum import IPADDRESS_TYPE
from maasserver.models import StaticIPAddress
from maasserver.models.dnsresource import DNSResource, separate_fqdn
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks, reload_object


class TestDNSResourceManagerGetDNSResourceOr404(MAASServerTestCase):
    def test_user_view_returns_dnsresource(self):
        user = factory.make_User()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, user, NodePermission.view
            ),
        )

    def test_user_edit_raises_PermissionError(self):
        user = factory.make_User()
        dnsresource = factory.make_DNSResource()
        self.assertRaises(
            PermissionDenied,
            DNSResource.objects.get_dnsresource_or_404,
            dnsresource.id,
            user,
            NodePermission.edit,
        )

    def test_user_admin_raises_PermissionError(self):
        user = factory.make_User()
        dnsresource = factory.make_DNSResource()
        self.assertRaises(
            PermissionDenied,
            DNSResource.objects.get_dnsresource_or_404,
            dnsresource.id,
            user,
            NodePermission.admin,
        )

    def test_admin_view_returns_dnsresource(self):
        admin = factory.make_admin()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, admin, NodePermission.view
            ),
        )

    def test_admin_edit_returns_dnsresource(self):
        admin = factory.make_admin()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, admin, NodePermission.edit
            ),
        )

    def test_admin_admin_returns_dnsresource(self):
        admin = factory.make_admin()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, admin, NodePermission.admin
            ),
        )


class TestDNSResourceManager(MAASServerTestCase):
    def test_default_specifier_matches_id(self):
        factory.make_DNSResource()
        dnsresource = factory.make_DNSResource()
        factory.make_DNSResource()
        id = dnsresource.id
        self.assertCountEqual(
            DNSResource.objects.filter_by_specifiers("%s" % id), [dnsresource]
        )

    def test_default_specifier_matches_name(self):
        factory.make_DNSResource()
        name = factory.make_name("dnsresource")
        dnsresource = factory.make_DNSResource(name=name)
        factory.make_DNSResource()
        self.assertCountEqual(
            DNSResource.objects.filter_by_specifiers(name), [dnsresource]
        )

    def test_name_specifier_matches_name(self):
        factory.make_DNSResource()
        name = factory.make_name("dnsresource")
        dnsresource = factory.make_DNSResource(name=name)
        factory.make_DNSResource()
        self.assertCountEqual(
            DNSResource.objects.filter_by_specifiers("name:%s" % name),
            [dnsresource],
        )


class TestDNSResource(MAASServerTestCase):
    def test_separate_fqdn_splits_srv(self):
        self.assertEqual(
            ("_sip._tcp.voip", "example.com"),
            separate_fqdn("_sip._tcp.voip.example.com", "SRV"),
        )

    def test_separate_fqdn_splits_nonsrv(self):
        self.assertEqual(
            ("foo", "test.example.com"),
            separate_fqdn("foo.test.example.com", "A"),
        )

    def test_separate_fqdn_returns_atsign_for_top_of_domain(self):
        name = "{}.{}.{}".format(
            factory.make_name("a"),
            factory.make_name("b"),
            factory.make_name("c"),
        )
        factory.make_Domain(name=name)
        self.assertEqual(("@", name), separate_fqdn(name))

    def test_separate_fqdn_allows_domain_override(self):
        parent = "{}.{}".format(factory.make_name("b"), factory.make_name("c"))
        label = "{}.{}".format(factory.make_name("a"), factory.make_name("d"))
        name = f"{label}.{parent}"
        factory.make_Domain(name=parent)
        self.assertEqual(
            (label, parent), separate_fqdn(name, domainname=parent)
        )

    def test_creates_dnsresource(self):
        name = factory.make_name("name")
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        # Should work without issue
        dnsresource.save()

    def test_allows_atsign(self):
        name = "@"
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        ip = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(ip)
        # Should work without issue
        dnsresource.save()

    def test_allows_wildcard(self):
        name = "*"
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        ip = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(ip)
        # Should work without issue
        dnsresource.save()

    def test_fqdn_returns_correctly_for_atsign(self):
        name = "@"
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        sip = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(sip)
        self.assertEqual(domain.name, dnsresource.fqdn)

    def test_allows_underscores_without_addresses(self):
        name = factory.make_name("n_me")
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        # Should work without issue
        dnsresource.save()

    def test_rejects_addresses_if_underscore_in_name(self):
        name = factory.make_name("n_me")
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        sip = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(sip)
        self.assertRaisesRegex(
            ValidationError,
            re.escape(f"{{'__all__': ['Invalid dnsresource name: {name}."),
            dnsresource.save,
            force_update=True,
        )

    def test_rejects_multiple_dnsresource_with_same_name(self):
        name = factory.make_name("name")
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        dnsresource2 = DNSResource(name=name, domain=domain)
        self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['Labels must be unique within their zone.']"
            ),
            dnsresource2.save,
            force_update=True,
        )

    def test_invalid_name_raises_exception(self):
        self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['Invalid dnsresource name: invalid*name.']"
            ),
            factory.make_DNSResource,
            name="invalid*name",
        )

    def test_underscore_label_raises_exception(self):
        self.assertRaises(
            ValidationError, factory.make_DNSResource, name="under_score"
        )

    def test_rejects_address_with_cname(self):
        name = factory.make_name("name")
        domain = factory.make_Domain()
        dnsdata = factory.make_DNSData(
            rrtype="CNAME", name=name, domain=domain
        )
        ipaddress = factory.make_StaticIPAddress()
        dnsrr = dnsdata.dnsresource
        dnsrr.ip_addresses.add(ipaddress)
        self.assertRaisesRegex(
            ValidationError,
            re.escape("{'__all__': ['Cannot add address: CNAME present.']"),
            dnsrr.save,
            force_update=True,
        )

    def test_get_addresses_returns_addresses(self):
        # Verify that the return includes node addresses, and
        # dnsresource-attached addresses.
        name = factory.make_name()
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, hostname=name, domain=domain
        )
        sip1 = factory.make_StaticIPAddress()
        node.current_config.interface_set.first().ip_addresses.add(sip1)
        sip2 = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(sip2)
        self.assertCountEqual(
            (sip1.get_ip(), sip2.get_ip()), dnsresource.get_addresses()
        )

    def test_delete_dnsresource(self):
        name = factory.make_name()
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, hostname=name, domain=domain
        )
        sip1 = factory.make_StaticIPAddress()
        node.current_config.interface_set.first().ip_addresses.add(sip1)
        sip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        dnsresource.ip_addresses.add(sip2)
        dnsresource.delete()
        assert StaticIPAddress.objects.filter(ip=sip1.get_ip()).exists()
        assert not StaticIPAddress.objects.filter(ip=sip2.get_ip()).exists()


class TestStaticIPAddressSignals(MAASServerTestCase):
    """Tests the signals signals/staticipaddress.py."""

    def test_deletes_orphaned_record(self):
        dnsrr = factory.make_DNSResource()
        StaticIPAddress.objects.all().delete()
        dnsrr = reload_object(dnsrr)
        self.assertIsNone(dnsrr)

    def test_non_orphaned_record_not_deleted(self):
        dnsrr = factory.make_DNSResource(ip_addresses=["8.8.8.8", "8.8.4.4"])
        sip = StaticIPAddress.objects.get(ip="8.8.4.4")

        with post_commit_hooks:
            sip.delete()
        dnsrr = reload_object(dnsrr)
        sip = StaticIPAddress.objects.get(ip="8.8.8.8")
        self.assertIn(sip, dnsrr.ip_addresses.all())
