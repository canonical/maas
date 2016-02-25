# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.domain`"""

__all__ = []

from django.core.exceptions import ValidationError
from maasserver.models import (
    DNSData,
    Domain,
    StaticIPAddress,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.domain import DomainHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from netaddr import IPAddress
from testtools.matchers import Equals


class TestDomainHandler(MAASServerTestCase):

    def dehydrate_domain(self, domain, for_list=False):
        data = {
            "id": domain.id,
            "name": domain.name,
            "authoritative": domain.authoritative,
            "ttl": None,
            "updated": dehydrate_datetime(domain.updated),
            "created": dehydrate_datetime(domain.created),
            }
        ip_map = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        rr_map = DNSData.objects.get_hostname_dnsdata_mapping(domain)
        domainname_len = len(domain.name)
        for name, info in ip_map.items():
            name = name[:-domainname_len - 1]
            if info.system_id is not None:
                rr_map[name].system_id = info.system_id
            for ip in info.ips:
                if IPAddress(ip).version == 4:
                    rr_map[name].rrset.add((info.ttl, 'A', ip))
                else:
                    rr_map[name].rrset.add((info.ttl, 'AAAA', ip))
        rrsets = [
            {
                'name': hostname,
                'system_id': info.system_id,
                'node_type': info.node_type,
                'ttl': ttl,
                'rrtype': rrtype,
                'rrdata': rrdata,
            }
            for hostname, info in rr_map.items()
            for ttl, rrtype, rrdata in info.rrset
        ]
        data['resource_count'] = len(rrsets)
        hosts = set()
        for record in rrsets:
            if record['system_id'] is not None:
                hosts.add(record['system_id'])
        data['hosts'] = len(hosts)
        if not for_list:
            data.update({
                "rrsets": rrsets,
            })
        return data

    def test_get(self):
        user = factory.make_User()
        handler = DomainHandler(user, {})
        domain = factory.make_Domain()
        factory.make_DNSData(domain=domain)
        factory.make_DNSResource(domain=domain)
        self.assertItemsEqual(
            self.dehydrate_domain(domain),
            handler.get({"id": domain.id}))

    def test_list(self):
        user = factory.make_User()
        handler = DomainHandler(user, {})
        factory.make_Domain()
        expected_domains = [
            self.dehydrate_domain(domain, for_list=True)
            for domain in Domain.objects.all()
            ]
        self.assertItemsEqual(
            expected_domains,
            handler.list({}))

    def test_create_raises_validation_error_for_missing_name(self):
        user = factory.make_User()
        handler = DomainHandler(user, {})
        params = {
            "name": ""
            }
        error = self.assertRaises(
            ValidationError, handler.create, params)
        self.assertThat(error.message_dict, Equals(
            {'name': ['This field cannot be blank.']}))
