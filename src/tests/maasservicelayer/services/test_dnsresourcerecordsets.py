#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
from unittest.mock import Mock

import pytest

from maascommon.dns import DomainDNSRecord
from maasservicelayer.models.dnsresourcerecordsets import (
    ARecord,
    DNSResourceRecordSet,
    DNSResourceTypeEnum,
    TXTRecord,
)
from maasservicelayer.services.dnsresourcerecordsets import (
    V3DNSResourceRecordSetsService,
)
from maasservicelayer.services.domains import DomainsService


@pytest.mark.asyncio
class TestV3DNSResourceRecordSetsService:
    async def test_get_rrsets_for_domain(self) -> None:
        domains_service = Mock(DomainsService)
        v3dnsrrsets_service = V3DNSResourceRecordSetsService(
            domains_service=domains_service
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

        rrsets_for_domains = await v3dnsrrsets_service.get_rrsets_for_domain(1)
        assert rrsets_for_domains == [
            DNSResourceRecordSet(
                name="example.com",
                node_id=1,
                ttl=30,
                rrtype=DNSResourceTypeEnum.A,
                a_records=[
                    ARecord(address=IPv4Address("10.0.0.2")),
                    ARecord(address=IPv4Address("10.0.0.3")),
                ],
            ),
            DNSResourceRecordSet(
                name="example.com",
                ttl=30,
                rrtype=DNSResourceTypeEnum.TXT,
                txt_records=[TXTRecord(txt_data="Some random text data.")],
            ),
        ]
