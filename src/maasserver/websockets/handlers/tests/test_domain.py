# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.domain`"""


from random import choice, randint

from django.core.exceptions import ValidationError
from netaddr import IPAddress
from testtools import ExpectedException
from testtools.matchers import Equals, HasLength, Is, Not

from maasserver.models import DNSData, DNSResource, Domain, StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.domain import DomainHandler


class TestDomainHandler(MAASServerTestCase):
    def dehydrate_domain(self, domain, for_list=False):
        if domain.id == 0:
            displayname = "%s (default)" % domain.name
        else:
            displayname = domain.name
        data = {
            "id": domain.id,
            "name": domain.name,
            "displayname": displayname,
            "authoritative": domain.authoritative,
            "ttl": domain.ttl,
            "updated": dehydrate_datetime(domain.updated),
            "created": dehydrate_datetime(domain.created),
            "is_default": domain.is_default(),
        }
        ip_map = StaticIPAddress.objects.get_hostname_ip_mapping(
            domain, raw_ttl=True
        )
        rr_map = DNSData.objects.get_hostname_dnsdata_mapping(
            domain, raw_ttl=True, with_ids=True
        )
        domainname_len = len(domain.name)
        for name, info in ip_map.items():
            name = name[: -domainname_len - 1]
            if info.system_id is not None:
                rr_map[name].system_id = info.system_id
            if info.user_id is not None:
                rr_map[name].user_id = info.user_id
            for ip in info.ips:
                if IPAddress(ip).version == 4:
                    rr_map[name].rrset.add((info.ttl, "A", ip, None))
                else:
                    rr_map[name].rrset.add((info.ttl, "AAAA", ip, None))
            rr_map[name].dnsresource_id = info.dnsresource_id
        rrsets = [
            {
                "name": hostname,
                "system_id": info.system_id,
                "node_type": info.node_type,
                "user_id": info.user_id,
                "dnsresource_id": info.dnsresource_id,
                "ttl": ttl,
                "rrtype": rrtype,
                "rrdata": rrdata,
                "dnsdata_id": dnsdata_id,
            }
            for hostname, info in rr_map.items()
            for ttl, rrtype, rrdata, dnsdata_id in info.rrset
        ]
        data["resource_count"] = len(rrsets)
        hosts = set()
        for record in rrsets:
            if record["system_id"] is not None:
                hosts.add(record["system_id"])
        data["hosts"] = len(hosts)
        if not for_list:
            data.update({"rrsets": rrsets})
        return data

    def test_get(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        factory.make_DNSData(domain=domain)
        factory.make_DNSResource(domain=domain)
        factory.make_DNSResource(domain=domain, address_ttl=randint(0, 300))
        self.assertEqual(
            self.dehydrate_domain(domain), handler.get({"id": domain.id})
        )

    def test_get_normal_user_only_owned_entries(self):
        user = factory.make_User()
        other_user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        hostname1 = factory.make_name("node")
        factory.make_Node_with_Interface_on_Subnet(
            hostname=hostname1, domain=domain, owner=user
        )
        dnsrr1 = factory.make_DNSResource(domain=domain, name=hostname1)
        factory.make_DNSData(dnsresource=dnsrr1, ip_addresses=True)
        hostname2 = factory.make_name("node")
        factory.make_Node_with_Interface_on_Subnet(
            hostname=hostname2, domain=domain, owner=other_user
        )
        dnsrr2 = factory.make_DNSResource(domain=domain, name=hostname2)
        factory.make_DNSData(dnsresource=dnsrr2, ip_addresses=True)
        details = handler.get({"id": domain.id})
        for entry in details["rrsets"]:
            self.assertEqual(entry["user_id"], user.id)

    def test_list(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        Domain.objects.get_default_domain()
        factory.make_Domain()
        expected_domains = [
            self.dehydrate_domain(domain, for_list=True)
            for domain in Domain.objects.all()
        ]
        self.assertItemsEqual(expected_domains, handler.list({}))

    def test_prevents_unauthorized_creation(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        params = {"name": ""}
        self.assertRaises(HandlerPermissionError, handler.create, params)

    def test_prevents_unauthorized_updates(self):
        user = factory.make_User()
        domain = Domain.objects.get_default_domain()
        new_name = factory.make_hostname()
        handler = DomainHandler(user, {}, None)
        with ExpectedException(HandlerPermissionError):
            handler.update({"id": domain.id, "name": new_name})

    def test_update_returns_model_object(self):
        user = factory.make_admin()
        domain = Domain.objects.get_default_domain()
        new_name = factory.make_hostname()
        handler = DomainHandler(user, {}, None)
        returned_domain = handler.update({"id": domain.id, "name": new_name})
        domain = reload_object(domain)
        self.assertThat(self.dehydrate_domain(domain), Equals(returned_domain))

    def test_update_allows_domain_name_change(self):
        user = factory.make_admin()
        domain = Domain.objects.get_default_domain()
        new_name = factory.make_hostname()
        handler = DomainHandler(user, {}, None)
        handler.update({"id": domain.id, "name": new_name})
        domain = reload_object(domain)
        self.assertThat(domain.name, Equals(new_name))

    def test_update_allows_default_ttl_change(self):
        user = factory.make_admin()
        domain = Domain.objects.get_default_domain()
        handler = DomainHandler(user, {}, None)
        new_ttl = randint(1, 3600)
        handler.update({"id": domain.id, "ttl": new_ttl})
        domain = reload_object(domain)
        self.assertThat(domain.ttl, Equals(new_ttl))

    def test_update_allows_authoritative_change(self):
        user = factory.make_admin()
        domain = factory.make_Domain(authoritative=choice([True, False]))
        handler = DomainHandler(user, {}, None)
        new_authoritative = not domain.authoritative
        handler.update({"id": domain.id, "authoritative": new_authoritative})
        domain = reload_object(domain)
        self.assertThat(domain.authoritative, Equals(new_authoritative))

    def test_update_raises_validaitonerror_for_empty_name(self):
        user = factory.make_admin()
        domain = factory.make_Domain(authoritative=choice([True, False]))
        handler = DomainHandler(user, {}, None)
        with ExpectedException(HandlerValidationError):
            handler.update({"id": domain.id, "name": ""})

    def test_create_raises_validation_error_for_missing_name(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        params = {"name": ""}
        error = self.assertRaises(
            HandlerValidationError, handler.create, params
        )
        self.assertThat(
            error.message_dict, Equals({"name": ["This field is required."]})
        )


class TestDomainHandlerDelete(MAASServerTestCase):
    def test_delete_as_admin_success(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        handler.delete({"id": domain.id})
        domain = reload_object(domain)
        self.assertThat(domain, Equals(None))

    def test_delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        with ExpectedException(HandlerPermissionError):
            handler.delete({"id": domain.id})

    def test_delete_default_domain_fails(self):
        domain = Domain.objects.get_default_domain()
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        with ExpectedException(ValidationError):
            handler.delete({"id": domain.id})


class TestDomainHandlerDNSResources(MAASServerTestCase):
    def test_add_resource(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        ttl = randint(1, 3600)
        handler.create_dnsresource(
            {
                "domain": domain.id,
                "name": name,
                "address_ttl": ttl,
                "ip_addresses": ["127.0.0.1"],
            }
        )
        resource = DNSResource.objects.get(domain=domain, name=name)
        self.assertThat(resource.address_ttl, Equals(ttl))
        self.assertThat(resource.name, Equals(name))
        self.assertThat(
            list(resource.ip_addresses.all())[0].ip, Equals("127.0.0.1")
        )

    def test_update_resource(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        new_name = factory.make_hostname()
        new_ttl = randint(1, 3600)
        handler.update_dnsresource(
            {
                "domain": domain.id,
                "dnsresource_id": resource.id,
                "name": new_name,
                "address_ttl": new_ttl,
                "ip_addresses": ["127.0.0.1"],
            }
        )
        resource = reload_object(resource)
        self.assertThat(resource.address_ttl, Equals(new_ttl))
        self.assertThat(resource.name, Equals(new_name))
        self.assertThat(
            list(resource.ip_addresses.all())[0].ip, Equals("127.0.0.1")
        )

    def test_update_resource_validation_error(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        self.assertRaises(
            ValidationError,
            handler.update_dnsresource,
            {
                "domain": domain.id,
                "dnsresource_id": resource.id,
                "address_ttl": "invalid",
            },
        )

    def test_delete_resource(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        handler.delete_dnsresource(
            {"domain": domain.id, "dnsresource_id": resource.id}
        )
        self.assertThat(reload_object(resource), Is(None))

    def test_add_resource_as_non_admin_fails(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        ttl = randint(1, 3600)
        with ExpectedException(HandlerPermissionError):
            handler.create_dnsresource(
                {
                    "domain": domain.id,
                    "name": name,
                    "address_ttl": ttl,
                    "ip_addresses": ["127.0.0.1"],
                }
            )

    def test_update_resource_as_non_admin_fails(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        new_name = factory.make_hostname()
        new_ttl = randint(1, 3600)
        with ExpectedException(HandlerPermissionError):
            handler.update_dnsresource(
                {
                    "domain": domain.id,
                    "dnsresource": resource.id,
                    "name": new_name,
                    "address_ttl": new_ttl,
                    "ip_addresses": ["127.0.0.1"],
                }
            )

    def test_delete_resource_as_non_admin_fails(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        with ExpectedException(HandlerPermissionError):
            handler.delete_dnsresource(
                {"domain": domain.id, "dnsresource": resource.id}
            )


class TestDomainHandlerDNSData(MAASServerTestCase):
    def test_add_data_for_new_resource_name(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        ttl = randint(1, 3600)
        handler.create_dnsdata(
            {
                "domain": domain.id,
                "name": name,
                "ttl": ttl,
                "rrtype": "TXT",
                "rrdata": "turtles all the way down",
            }
        )
        dnsresource = DNSResource.objects.get(domain=domain, name=name)
        # Expect that a single DNSData object is associated with the resource.
        [dnsdata] = dnsresource.dnsdata_set.all()
        self.expectThat(dnsresource.name, Equals(name))
        self.expectThat(dnsdata.rrtype, Equals("TXT"))
        self.expectThat(dnsdata.rrdata, Equals("turtles all the way down"))
        self.expectThat(dnsdata.ttl, Equals(ttl))

    def test_add_data_for_new_resource_name_fails_for_non_admin(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        ttl = randint(1, 3600)
        with ExpectedException(HandlerPermissionError):
            handler.create_dnsdata(
                {
                    "domain": domain.id,
                    "name": name,
                    "ttl": ttl,
                    "rrtype": "TXT",
                    "rrdata": "turtles all the way down",
                }
            )
        with ExpectedException(DNSResource.DoesNotExist):
            DNSResource.objects.get(domain=domain, name=name)

    def test_add_data_for_existing_resource_name(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        dnsresource = factory.make_DNSResource(domain=domain, name=name)
        ttl = randint(1, 3600)
        handler.create_dnsdata(
            {
                "domain": domain.id,
                "name": name,
                "ttl": ttl,
                "rrtype": "TXT",
                "rrdata": "turtles all the way down",
            }
        )
        # Expect that a single DNSData object is associated with the resource.
        [dnsdata] = dnsresource.dnsdata_set.all()
        self.expectThat(dnsresource.name, Equals(name))
        self.expectThat(dnsdata.rrtype, Equals("TXT"))
        self.expectThat(dnsdata.rrdata, Equals("turtles all the way down"))
        self.expectThat(dnsdata.ttl, Equals(ttl))

    def test_add_data_for_existing_resource_name_fails_for_non_admin(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        dnsresource = factory.make_DNSResource(domain=domain, name=name)
        ttl = randint(1, 3600)
        with ExpectedException(HandlerPermissionError):
            handler.create_dnsdata(
                {
                    "domain": domain.id,
                    "name": name,
                    "ttl": ttl,
                    "rrtype": "TXT",
                    "rrdata": "turtles all the way down",
                }
            )
        self.expectThat(dnsresource.dnsdata_set.all(), HasLength(0))

    def test_update_dnsdata(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        dnsresource = factory.make_DNSResource(domain=domain)
        dnsdata = factory.make_DNSData(
            dnsresource, rrtype="TXT", rrdata="original"
        )
        handler.update_dnsdata(
            {
                "domain": domain.id,
                "dnsresource_id": dnsresource.id,
                "dnsdata_id": dnsdata.id,
                "rrdata": "updated",
            }
        )
        dnsdata = reload_object(dnsdata)
        self.assertThat(dnsdata.rrdata, Equals("updated"))

    def test_update_dnsdata_fails_for_non_admin(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        dnsresource = factory.make_DNSResource(domain=domain)
        dnsdata = factory.make_DNSData(
            dnsresource, rrtype="TXT", rrdata="original"
        )
        with ExpectedException(HandlerPermissionError):
            handler.update_dnsdata(
                {
                    "domain": domain.id,
                    "dnsresource_id": dnsresource.id,
                    "dnsdata_id": dnsdata.id,
                    "rrdata": "updated",
                }
            )
        dnsdata = reload_object(dnsdata)
        self.assertThat(dnsdata.rrdata, Equals("original"))

    def test_delete_dnsdata(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        dnsresource = factory.make_DNSResource(domain=domain)
        dnsdata = factory.make_DNSData(dnsresource)
        handler.delete_dnsdata({"domain": domain.id, "dnsdata_id": dnsdata.id})
        dnsdata = reload_object(dnsdata)
        self.assertThat(dnsdata, Is(None))

    def test_delete_dnsdata_fails_for_non_admin(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        dnsresource = factory.make_DNSResource(domain=domain)
        dnsdata = factory.make_DNSData(dnsresource)
        with ExpectedException(HandlerPermissionError):
            handler.delete_dnsdata(
                {"domain": domain.id, "dnsdata_id": dnsdata.id}
            )
        dnsdata = reload_object(dnsdata)
        self.assertThat(dnsdata, Not(Is(None)))


class TestDomainHandlerAddressRecords(MAASServerTestCase):
    def test_add_address_record(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        ttl = randint(1, 3600)
        handler.create_address_record(
            {
                "domain": domain.id,
                "name": name,
                "address_ttl": ttl,
                "ip_addresses": ["127.0.0.1"],
            }
        )
        resource = DNSResource.objects.get(domain=domain, name=name)
        self.assertThat(resource.address_ttl, Equals(ttl))
        self.assertThat(resource.name, Equals(name))
        self.assertThat(
            list(resource.ip_addresses.all())[0].ip, Equals("127.0.0.1")
        )

    def test_add_two_addresses_in_succession(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        ttl = randint(1, 3600)
        handler.create_address_record(
            {
                "domain": domain.id,
                "name": name,
                "address_ttl": ttl,
                "ip_addresses": ["127.0.0.1"],
            }
        )
        handler.create_address_record(
            {
                "domain": domain.id,
                "name": name,
                "address_ttl": ttl,
                "ip_addresses": ["127.0.0.2"],
            }
        )
        resource = DNSResource.objects.get(domain=domain, name=name)
        self.assertThat(resource.address_ttl, Equals(ttl))
        self.assertThat(resource.name, Equals(name))
        self.assertCountEqual(
            resource.get_addresses(), ["127.0.0.1", "127.0.0.2"]
        )

    def test_update_address__updates_single_address(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        resource = factory.make_DNSResource(
            domain=domain, name=name, ip_addresses=["127.0.0.1", "127.0.0.2"]
        )
        handler.update_address_record(
            {
                "domain": domain.id,
                "dnsresource_id": resource.id,
                "previous_name": resource.name,
                "previous_rrdata": "127.0.0.1",
                "name": name,
                "ip_addresses": ["127.0.0.3"],
            }
        )
        resource = reload_object(resource)
        self.assertCountEqual(
            resource.get_addresses(), ["127.0.0.2", "127.0.0.3"]
        )

    def test_update_address__creates_second_dnsrecord_if_name_changed(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(
            domain=domain, name="foo", ip_addresses=["127.0.0.1", "127.0.0.2"]
        )
        handler.update_address_record(
            {
                "domain": domain.id,
                "dnsresource_id": resource.id,
                "previous_name": resource.name,
                "previous_rrdata": "127.0.0.1",
                "name": "bar",
                "ip_addresses": ["127.0.0.3"],
            }
        )
        resource = reload_object(resource)
        self.assertThat(resource.get_addresses(), Equals(["127.0.0.2"]))
        resource = DNSResource.objects.get(domain=domain, name="bar")
        self.assertThat(resource.get_addresses(), Equals(["127.0.0.3"]))

    def test_delete_address_deletes_single_address(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        resource = factory.make_DNSResource(
            domain=domain, name=name, ip_addresses=["127.0.0.1", "127.0.0.2"]
        )
        handler.delete_address_record(
            {
                "domain": domain.id,
                "dnsresource_id": resource.id,
                "rrdata": "127.0.0.1",
            }
        )
        self.assertThat(resource.get_addresses(), Equals(["127.0.0.2"]))

    def test_add_address_as_non_admin_fails(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        ttl = randint(1, 3600)
        with ExpectedException(HandlerPermissionError):
            handler.create_address_record(
                {
                    "domain": domain.id,
                    "name": name,
                    "address_ttl": ttl,
                    "ip_addresses": ["127.0.0.1"],
                }
            )

    def test_add_address_without_ip_addresses_fails(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        name = factory.make_hostname()
        with ExpectedException(ValidationError):
            handler.create_address_record(
                {
                    "domain": domain.id,
                    "name": name,
                    "rrtype": choice(["A", "AAAA"]),
                    "ip_addresses": [""],
                }
            )

    def test_update_address_as_non_admin_fails(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        new_name = factory.make_hostname()
        new_ttl = randint(1, 3600)
        with ExpectedException(HandlerPermissionError):
            handler.update_address_record(
                {
                    "domain": domain.id,
                    "dnsresource": resource.id,
                    "name": new_name,
                    "address_ttl": new_ttl,
                    "ip_addresses": ["127.0.0.1"],
                }
            )

    def test_delete_resource_as_non_admin_fails(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        with ExpectedException(HandlerPermissionError):
            handler.delete_address_record(
                {"domain": domain.id, "dnsresource": resource.id}
            )

    def test_set_default_sets_default(self):
        user = factory.make_admin()
        handler = DomainHandler(user, {}, None)
        factory.make_Domain()
        domain2 = factory.make_Domain()
        self.assertThat(domain2.is_default(), Equals(False))
        handler.set_default({"domain": domain2.id})
        domain2 = reload_object(domain2)
        self.assertThat(domain2.is_default(), Equals(True))

    def test_set_default_as_non_admin_fails(self):
        user = factory.make_User()
        handler = DomainHandler(user, {}, None)
        domain = factory.make_Domain()
        with ExpectedException(HandlerPermissionError):
            handler.set_default({"domain": domain.id})
