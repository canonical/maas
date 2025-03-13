#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.dns import DomainDNSRecord
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.dnsdata import DNSDataBuilder
from maasservicelayer.builders.dnsresources import DNSResourceBuilder
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.models.dnsresourcerecordsets import (
    DNSResourceTypeEnum,
    GenericDNSRecord,
)
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services.dnsdata import DNSDataService
from maasservicelayer.services.dnsresourcerecordsets import (
    V3DNSResourceRecordSetsService,
)
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService


@pytest.mark.asyncio
class TestV3DNSResourceRecordSetsService:
    async def test_get_dns_records_for_domain(self) -> None:
        domains_service = Mock(DomainsService)
        v3dnsrrsets_service = V3DNSResourceRecordSetsService(
            context=Mock(Context),
            domains_service=domains_service,
            dnsresource_service=Mock(DNSResourcesService),
            dnsdata_service=Mock(DNSDataService),
            staticipaddress_service=Mock(StaticIPAddressService),
            subnets_service=Mock(SubnetsService),
        )
        domains_service.v3_render_json_for_related_rrdata.return_value = {
            "example.com": [
                DomainDNSRecord(
                    name="example.com",
                    system_id="abcdef",
                    node_type=None,
                    user_id=None,
                    dnsresource_id=None,
                    node_id=1,
                    ttl=30,
                    rrtype=DNSResourceTypeEnum.A,
                    rrdata="10.0.0.2",
                    dnsdata_id=None,
                ),
                DomainDNSRecord(
                    name="example.com",
                    system_id="abcdef",
                    node_type=None,
                    user_id=None,
                    dnsresource_id=None,
                    node_id=1,
                    ttl=30,
                    rrtype=DNSResourceTypeEnum.A,
                    rrdata="10.0.0.3",
                    dnsdata_id=None,
                ),
                DomainDNSRecord(
                    name="example.com",
                    system_id="abcdef",
                    node_type=None,
                    user_id=None,
                    dnsresource_id=None,
                    node_id=None,
                    ttl=30,
                    rrtype=DNSResourceTypeEnum.TXT,
                    rrdata="Some random text data.",
                    dnsdata_id=None,
                ),
            ]
        }

        rrsets_for_domains = (
            await v3dnsrrsets_service.get_dns_records_for_domain(1)
        )
        assert rrsets_for_domains == [
            GenericDNSRecord(
                name="example.com",
                node_id=1,
                ttl=30,
                rrtype=DNSResourceTypeEnum.A,
                rrdatas=[
                    "10.0.0.2",
                    "10.0.0.3",
                ],
            ),
            GenericDNSRecord(
                name="example.com",
                ttl=30,
                rrtype=DNSResourceTypeEnum.TXT,
                rrdatas=["Some random text data."],
            ),
        ]

    @pytest.mark.parametrize(
        "dns_record",
        [
            GenericDNSRecord(
                name="foo", rrtype=DNSResourceTypeEnum.A, rrdatas=["10.10.0.2"]
            ),
            GenericDNSRecord(
                name="foo",
                rrtype=DNSResourceTypeEnum.A,
                rrdatas=["10.10.0.2", "10.10.0.3"],
            ),
            GenericDNSRecord(
                name="foo",
                rrtype=DNSResourceTypeEnum.AAAA,
                rrdatas=["2001:db8:3333:4444:5555:6666:7777:8888"],
            ),
            GenericDNSRecord(
                name="foo",
                rrtype=DNSResourceTypeEnum.AAAA,
                rrdatas=[
                    "2001:db8:3333:4444:5555:6666:7777:8888",
                    "2001:db8:3333:4444:CCCC:DDDD:EEEE:FFFF",
                ],
            ),
        ],
    )
    async def test_create_a_aaaa_dns_records_for_domain(
        self, dns_record: GenericDNSRecord
    ) -> None:
        domains_service = Mock(DomainsService)
        dnsresource_service = Mock(DNSResourcesService)
        dnsdata_service = Mock(DNSDataService)
        staticipaddress_service = Mock(StaticIPAddressService)
        subnets_service = Mock(SubnetsService)
        domains_service.get_by_id.return_value = Domain(
            id=0, name="maas", authoritative=True
        )
        dnsresource_service.get_one.return_value = DNSResource(
            id=1, name="foo", domain_id=0
        )
        staticipaddress_service.get_one.return_value = None
        subnets_service.find_best_subnet_for_ip.return_value = None
        staticipaddress_service.create.return_value = StaticIPAddress(
            id=1, alloc_type=IpAddressType.USER_RESERVED, lease_time=0
        )
        v3dnsrrsets_service = V3DNSResourceRecordSetsService(
            context=Mock(Context),
            domains_service=domains_service,
            dnsresource_service=dnsresource_service,
            dnsdata_service=dnsdata_service,
            staticipaddress_service=staticipaddress_service,
            subnets_service=subnets_service,
        )
        await v3dnsrrsets_service.create_dns_records_for_domain(
            domain_id=0, dns_record=dns_record, user_id=0
        )
        for rrdata in dns_record.rrdatas:
            staticipaddress_service.create.assert_any_call(
                StaticIPAddressBuilder(
                    ip=rrdata,
                    alloc_type=IpAddressType.USER_RESERVED,
                    user_id=0,
                    subnet_id=None,
                    lease_time=0,
                )
            )
            dnsresource_service.link_ip.assert_called()

    @pytest.mark.parametrize(
        "dns_record",
        [
            GenericDNSRecord(
                name="foo",
                rrtype=DNSResourceTypeEnum.MX,
                rrdatas=["mailhost.example.com 1"],
            ),
            GenericDNSRecord(
                name="foo",
                rrtype=DNSResourceTypeEnum.NS,
                rrdatas=["nsdname1", "nsdname2"],
            ),
            GenericDNSRecord(
                name="foo",
                rrtype=DNSResourceTypeEnum.SRV,
                rrdatas=["_xmpp._tcp.example.com"],
            ),
            GenericDNSRecord(
                name="foo",
                rrtype=DNSResourceTypeEnum.TXT,
                rrdatas=["data1", "data2"],
            ),
        ],
    )
    async def test_create_other_dns_records_for_domain(
        self, dns_record: GenericDNSRecord
    ) -> None:
        domains_service = Mock(DomainsService)
        dnsresource_service = Mock(DNSResourcesService)
        dnsdata_service = Mock(DNSDataService)
        staticipaddress_service = Mock(StaticIPAddressService)
        subnets_service = Mock(SubnetsService)
        domains_service.get_by_id.return_value = Domain(
            id=0, name="maas", authoritative=True
        )
        dnsresource_service.get_one.return_value = DNSResource(
            id=1, name="foo", domain_id=0
        )
        dnsdata_service.exists.return_value = False
        dnsresource_service.get_ips_for_dnsresource.return_value = []
        v3dnsrrsets_service = V3DNSResourceRecordSetsService(
            context=Mock(Context),
            domains_service=domains_service,
            dnsresource_service=dnsresource_service,
            dnsdata_service=dnsdata_service,
            staticipaddress_service=staticipaddress_service,
            subnets_service=subnets_service,
        )
        await v3dnsrrsets_service.create_dns_records_for_domain(
            domain_id=0, dns_record=dns_record, user_id=0
        )
        for rrdata in dns_record.rrdatas:
            dnsdata_service.create.assert_any_call(
                DNSDataBuilder(
                    dnsresource_id=1,
                    ttl=None,
                    rrtype=dns_record.rrtype,
                    rrdata=rrdata,
                )
            )

    @pytest.mark.parametrize(
        "dns_record, resource_builder",
        [
            (
                GenericDNSRecord(
                    name="foo",
                    rrtype=DNSResourceTypeEnum.TXT,
                    rrdatas=["data"],
                ),
                DNSResourceBuilder(name="foo", domain_id=0),
            ),
            (
                GenericDNSRecord(
                    name="foo",
                    rrtype=DNSResourceTypeEnum.A,
                    rrdatas=["10.10.10.10"],
                ),
                DNSResourceBuilder(name="foo", address_ttl=None, domain_id=0),
            ),
            (
                GenericDNSRecord(
                    name="foo",
                    ttl=50,
                    rrtype=DNSResourceTypeEnum.A,
                    rrdatas=["10.10.10.10"],
                ),
                DNSResourceBuilder(name="foo", address_ttl=50, domain_id=0),
            ),
        ],
    )
    async def test_create_dns_records_creates_dns_resource(
        self,
        dns_record: GenericDNSRecord,
        resource_builder: DNSResourceBuilder,
    ) -> None:
        domains_service = Mock(DomainsService)
        dnsresource_service = Mock(DNSResourcesService)
        dnsdata_service = Mock(DNSDataService)
        staticipaddress_service = Mock(StaticIPAddressService)
        subnets_service = Mock(SubnetsService)
        domains_service.get_by_id.return_value = Domain(
            id=0, name="maas", authoritative=True
        )
        dnsresource_service.get_one.return_value = None
        dnsdata_service.exists.return_value = False
        dnsresource_service.get_ips_for_dnsresource.return_value = []
        v3dnsrrsets_service = V3DNSResourceRecordSetsService(
            context=Mock(Context),
            domains_service=domains_service,
            dnsresource_service=dnsresource_service,
            dnsdata_service=dnsdata_service,
            staticipaddress_service=staticipaddress_service,
            subnets_service=subnets_service,
        )
        await v3dnsrrsets_service.create_dns_records_for_domain(
            domain_id=0, dns_record=dns_record, user_id=0
        )
        dnsresource_service.create.assert_called_once_with(resource_builder)
