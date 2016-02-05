# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.domain`"""

__all__ = []

from maasserver.models import (
    DNSData,
    Domain,
    StaticIPAddress,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.domain import DomainHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime


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
        ip_addresses = [
            {
                # strip off the domain name.
                'hostname': hostname[:-domainname_len - 1],
                'system_id': info.system_id,
                'ttl': info.ttl,
                'ips': info.ips}
            for hostname, info in ip_map.items()
        ]
        rrsets = [
            {
                'hostname': hostname,
                'system_id': info.system_id,
                'rrsets': info.rrset,
            }
            for hostname, info in rr_map.items()
        ]
        count = 0
        for record in ip_addresses:
            count += len(record['ips'])
        for record in rrsets:
            count += len(record['rrsets'])
        data['resource_count'] = count
        if not for_list:
            data.update({
                "ip_addresses": ip_addresses,
                "rrsets": rrsets,
            })
        return data

    def test_get(self):
        user = factory.make_User()
        handler = DomainHandler(user, {})
        domain = factory.make_Domain()
        factory.make_DNSData(domain=domain)
        factory.make_DNSResource(domain=domain)
        self.assertEqual(
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
