# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import timedelta
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from maasserver.enum import IPADDRESS_TYPE
from maasserver.models import StaticIPAddress
from maasserver.models.dnsresource import DNSResource, separate_fqdn
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


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
                "{'__all__': " "['Labels must be unique within their zone.']"
            ),
            dnsresource2.save,
            force_update=True,
        )

    def test_invalid_name_raises_exception(self):
        self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': " "['Invalid dnsresource name: invalid*name.']"
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
            re.escape("{'__all__': " "['Cannot add address: CNAME present.']"),
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


class TestUpdateDynamicHostname(MAASServerTestCase):
    def test_adds_new_hostname(self):
        sip = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip, hostname)
        dnsrr = DNSResource.objects.get(name=hostname)
        self.assertIn(sip, dnsrr.ip_addresses.all())

    def test_coerces_to_valid_hostname(self):
        sip = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = "no tea"
        DNSResource.objects.update_dynamic_hostname(sip, hostname)
        dnsrr = DNSResource.objects.get(name="no-tea")
        self.assertIn(sip, dnsrr.ip_addresses.all())

    def test_does_not_modify_existing_non_dynamic_records(self):
        sip_reserved = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        hostname = factory.make_name().lower()
        factory.make_DNSResource(name=hostname, ip_addresses=[sip_reserved])
        sip_dynamic = factory.make_StaticIPAddress(
            ip="10.0.0.2", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        DNSResource.objects.update_dynamic_hostname(sip_dynamic, hostname)
        dnsrr = DNSResource.objects.get(name=hostname)
        self.assertIn(sip_reserved, dnsrr.ip_addresses.all())
        self.assertNotIn(sip_dynamic, dnsrr.ip_addresses.all())

    def test_updates_existing_dynamic_record(self):
        sip_before = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip_before, hostname)
        sip_after = factory.make_StaticIPAddress(
            ip="10.0.0.2", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        DNSResource.objects.update_dynamic_hostname(sip_after, hostname)
        dnsrr = DNSResource.objects.get(name=hostname)
        self.assertIn(sip_after, dnsrr.ip_addresses.all())
        self.assertIn(sip_before, dnsrr.ip_addresses.all())

    def test_skips_updating_already_added_ip(self):
        sip1 = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        sip2 = factory.make_StaticIPAddress(
            ip="10.0.0.2", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip1, hostname)
        DNSResource.objects.update_dynamic_hostname(sip2, hostname)
        dnsrr = DNSResource.objects.get(name=hostname)
        # Create a date object for one week ago.
        before = timezone.now() - timedelta(days=7)
        dnsrr.save(_created=before, _updated=before, force_update=True)
        dnsrr = DNSResource.objects.get(name=hostname)
        self.assertEqual(before, dnsrr.updated)
        self.assertEqual(before, dnsrr.created)
        # Test that the timestamps weren't updated after updating again.
        DNSResource.objects.update_dynamic_hostname(sip1, hostname)
        DNSResource.objects.update_dynamic_hostname(sip2, hostname)
        dnsrr = DNSResource.objects.get(name=hostname)
        self.assertEqual(before, dnsrr.updated)
        self.assertEqual(before, dnsrr.created)

    def test_update_releases_obsolete_hostnames(self):
        sip = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname_old = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip, hostname_old)
        hostname_new = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip, hostname_new)
        dnsrr = DNSResource.objects.get(name=hostname_new)
        self.assertIn(sip, dnsrr.ip_addresses.all())
        self.assertIsNone(
            DNSResource.objects.filter(name=hostname_old).first()
        )


class TestReleaseDynamicHostname(MAASServerTestCase):
    def test_releases_dynamic_hostname(self):
        sip = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip, hostname)
        DNSResource.objects.release_dynamic_hostname(sip)
        self.assertIsNone(DNSResource.objects.filter(name=hostname).first())

    def test_releases_dynamic_hostname_keep_others(self):
        sip1 = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        sip2 = factory.make_StaticIPAddress(
            ip="10.0.0.2", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip1, hostname)
        DNSResource.objects.update_dynamic_hostname(sip2, hostname)
        DNSResource.objects.release_dynamic_hostname(sip2)
        dns_resource = DNSResource.objects.get(name=hostname)
        self.assertEqual([sip1], list(dns_resource.ip_addresses.all()))

    def test_no_update_not_there(self):
        sip1 = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        sip2 = factory.make_StaticIPAddress(
            ip="10.0.0.2", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip1, hostname)
        before = timezone.now() - timedelta(days=7)
        dns_resource = DNSResource.objects.get(name=hostname)
        dns_resource.save(_created=before, _updated=before, force_update=True)
        DNSResource.objects.release_dynamic_hostname(sip2)
        dns_resource = DNSResource.objects.get(name=hostname)
        self.assertEqual([sip1], list(dns_resource.ip_addresses.all()))
        self.assertEqual(before, dns_resource.updated)

    def test_leaves_static_hostnames_untouched(self):
        sip = factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        hostname = factory.make_name().lower()
        DNSResource.objects.update_dynamic_hostname(sip, hostname)
        sip_reserved = factory.make_StaticIPAddress(
            ip="10.0.0.2", alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        dnsrr = DNSResource.objects.get(name=hostname)
        dnsrr.ip_addresses.add(sip_reserved)
        DNSResource.objects.release_dynamic_hostname(sip)
        dnsrr = reload_object(dnsrr)
        self.assertIn(sip_reserved, dnsrr.ip_addresses.all())
        self.assertNotIn(sip, dnsrr.ip_addresses.all())


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
        sip.delete()
        dnsrr = reload_object(dnsrr)
        sip = StaticIPAddress.objects.get(ip="8.8.8.8")
        self.assertIn(sip, dnsrr.ip_addresses.all())
