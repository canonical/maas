# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

import pytest

from maasapiserver.v3.api.public.models.dnsresourcerecordsets import (
    AAAARecord,
    ARecord,
    CNAMERecord,
    MXRecord,
    NSRecord,
    SRVRecord,
    SSHFPRecord,
    TXTRecord,
)
from maasapiserver.v3.api.public.models.responses.domains import (
    AAAARecordResponse,
    ARecordResponse,
    CNAMERecordResponse,
    DomainResourceRecordSetResponse,
    DomainResponse,
    MXRecordResponse,
    NSRecordResponse,
    SRVRecordResponse,
    SSHFPRecordResponse,
    TXTRecordResponse,
)
from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.models.dnsresourcerecordsets import GenericDNSRecord
from maasservicelayer.models.domains import Domain


class TestDomainResponse:
    def test_from_model(self) -> None:
        domain = Domain(id=0, name="maas", authoritative=True, ttl=30)
        domain_response = DomainResponse.from_model(
            domain, self_base_hyperlink="http://test"
        )
        assert domain_response.kind == "Domain"
        assert domain_response.id == domain.id
        assert domain_response.name == domain.name
        assert domain_response.authoritative == domain.authoritative
        assert domain_response.ttl == domain.ttl
        assert (
            domain_response.hal_links.self.href == f"http://test/{domain.id}"
        )


class TestARecordResponse:
    def test_from_model(self) -> None:
        record = ARecord(address=IPv4Address("10.0.0.2"))
        record_response = ARecordResponse.from_model(record)
        assert record_response.kind == "ARecord"
        assert record_response.ipv4address == record.address


class TestAAAARecordResponse:
    def test_from_model(self) -> None:
        record = AAAARecord(address=IPv6Address("2001:db8::"))
        record_response = AAAARecordResponse.from_model(record)
        assert record_response.kind == "AAAARecord"
        assert record_response.ipv6address == record.address


class TestCNAMERecordResponse:
    def test_from_model(self) -> None:
        record = CNAMERecord(cname="example")
        record_response = CNAMERecordResponse.from_model(record)
        assert record_response.kind == "CNAMERecord"
        assert record_response.cname == record.cname


class TestMXRecordResponse:
    def test_from_model(self) -> None:
        record = MXRecord(exchange="mailhost.example.com", preference=1)
        record_response = MXRecordResponse.from_model(record)
        assert record_response.kind == "MXRecord"
        assert record_response.exchange == record.exchange
        assert record_response.preference == record.preference


class TestNSRecordResponse:
    def test_from_model(self) -> None:
        record = NSRecord(nsdname="example.com")
        record_response = NSRecordResponse.from_model(record)
        assert record_response.kind == "NSRecord"
        assert record_response.nsdname == record.nsdname


class TestSSHFPRecordResponse:
    def test_from_model(self) -> None:
        record = SSHFPRecord(
            algorithm=0, fingerprint_type=0, fingerprint="test"
        )
        record_response = SSHFPRecordResponse.from_model(record)
        assert record_response.kind == "SSHFPRecord"
        assert record_response.algorithm == record.algorithm
        assert record_response.fingerprint_type == record.fingerprint_type
        assert record_response.fingerprint == record.fingerprint


class TestSRVRecordResponse:
    def test_from_model(self) -> None:
        record = SRVRecord(
            port=9000, priority=1, target="server.example.com", weight=5
        )
        record_response = SRVRecordResponse.from_model(record)
        assert record_response.kind == "SRVRecord"
        assert record_response.port == record.port
        assert record_response.priority == record.priority
        assert record_response.target == record.target
        assert record_response.weight == record.weight


class TestTXTRecordResponse:
    def test_from_model(self) -> None:
        record = TXTRecord(data="test")
        record_response = TXTRecordResponse.from_model(record)
        assert record_response.kind == "TXTRecord"
        assert record_response.data == record.data


class TestDomainResourceRecordSetResponse:
    @pytest.mark.parametrize(
        "rrset",
        [
            GenericDNSRecord(
                name="example.com",
                rrtype=DNSResourceTypeEnum.A,
                rrdatas=["10.0.0.2"],
            ),
            GenericDNSRecord(
                name="example.com",
                rrtype=DNSResourceTypeEnum.AAAA,
                rrdatas=["2001:db8::"],
            ),
            GenericDNSRecord(
                name="example.com",
                rrtype=DNSResourceTypeEnum.CNAME,
                rrdatas=["example"],
            ),
            GenericDNSRecord(
                name="example.com",
                rrtype=DNSResourceTypeEnum.MX,
                rrdatas=["1 mailhost.example.com"],
            ),
            GenericDNSRecord(
                name="example.com",
                rrtype=DNSResourceTypeEnum.NS,
                rrdatas=["example.com"],
            ),
            GenericDNSRecord(
                name="example.com",
                rrtype=DNSResourceTypeEnum.SSHFP,
                rrdatas=["0 0 abcd"],
            ),
            GenericDNSRecord(
                name="_xmpp._tcp.example.com",
                rrtype=DNSResourceTypeEnum.SRV,
                rrdatas=[
                    "10 5 5223 server.example.com",
                ],
            ),
            GenericDNSRecord(
                name="example.com",
                rrtype=DNSResourceTypeEnum.TXT,
                rrdatas=["test"],
            ),
        ],
    )
    def test_from_model(self, rrset: GenericDNSRecord) -> None:
        response = DomainResourceRecordSetResponse.from_model(
            rrset, self_base_hyperlink="http://test"
        )
        assert response.kind == "DomainResourceRecordSet"
        assert response.name == rrset.name
        assert response.node_id == rrset.node_id
        assert response.ttl == rrset.ttl
        assert response.rrtype == rrset.rrtype
        match rrset.rrtype:
            case DNSResourceTypeEnum.A:
                assert response.a_records is not None
                assert len(response.a_records) == 1
            case DNSResourceTypeEnum.AAAA:
                assert response.aaaa_records is not None
                assert len(response.aaaa_records) == 1
            case DNSResourceTypeEnum.CNAME:
                assert response.cname_record is not None
            case DNSResourceTypeEnum.MX:
                assert response.mx_records is not None
                assert len(response.mx_records) == 1
            case DNSResourceTypeEnum.NS:
                assert response.ns_records is not None
                assert len(response.ns_records) == 1
            case DNSResourceTypeEnum.SSHFP:
                assert response.sshfp_records is not None
                assert len(response.sshfp_records) == 1
            case DNSResourceTypeEnum.SRV:
                assert response.srv_records is not None
                assert len(response.srv_records) == 1
            case DNSResourceTypeEnum.TXT:
                assert response.txt_records is not None
                assert len(response.txt_records) == 1

        assert response.hal_links.self.href == "http://test"
