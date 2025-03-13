#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.dnsresourcerecordsets import (
    AAAARecord,
    ARecord,
    SRVRecord,
)
from maasapiserver.v3.api.public.models.requests.domains import (
    DNSResourceRecordSetRequest,
    DomainRequest,
)
from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.exceptions.catalog import ValidationException


class TestDomainRequest:
    def test_mandatory_params(self) -> None:
        with pytest.raises(ValidationError) as e:
            DomainRequest()
        assert len(e.value.errors()) == 1
        assert "name" in (e.value.errors()[0]["loc"][0])

    @pytest.mark.parametrize(
        "ttl, valid",
        [
            (1, True),
            (604800, True),
            (0, False),
            (604801, False),
        ],
    )
    def test_check_ttl(self, ttl: int, valid: bool) -> None:
        if not valid:
            with pytest.raises(ValidationError):
                DomainRequest(
                    name="name",
                    ttl=ttl,
                )
        else:
            DomainRequest(
                name="name",
                ttl=ttl,
            )

    def test_to_builder(self) -> None:
        dr = DomainRequest(
            name="domain-name",
        )
        b = dr.to_builder()
        assert dr.name == b.name


class TestDNSResourceRecordSetRequest:
    @pytest.mark.parametrize(
        "name, should_raise",
        [
            ("@", False),
            ("*", False),
            ("_xmpp._tcp.example.com", False),
            ("foo.bar.example.com", True),
        ],
    )
    def test_domain_name_validation_srv(
        self, name: str, should_raise: bool
    ) -> None:
        record = SRVRecord(
            priority=10, weight=5, port=5223, target="server.example.com"
        )
        if should_raise:
            with pytest.raises(ValidationError):
                DNSResourceRecordSetRequest(
                    name=name,
                    rrtype=DNSResourceTypeEnum.SRV,
                    srv_records=[record],
                )
        else:
            DNSResourceRecordSetRequest(
                name=name, rrtype=DNSResourceTypeEnum.SRV, srv_records=[record]
            )

    @pytest.mark.parametrize(
        "name, should_raise",
        [
            ("@", False),
            ("*", False),
            ("foo.bar.example.com", False),
            ("_xmpp._tcp.example.com", True),
        ],
    )
    def test_domain_name_validation_others(
        self, name: str, should_raise: bool
    ) -> None:
        record = ARecord(address=IPv4Address("10.10.10.10"))
        if should_raise:
            with pytest.raises(ValidationError):
                DNSResourceRecordSetRequest(
                    name=name, rrtype=DNSResourceTypeEnum.A, a_records=[record]
                )
        else:
            DNSResourceRecordSetRequest(
                name=name, rrtype=DNSResourceTypeEnum.A, a_records=[record]
            )

    def test_ensure_only_one_record_set(self) -> None:
        DNSResourceRecordSetRequest(
            name="foo",
            rrtype=DNSResourceTypeEnum.A,
            a_records=[ARecord(address=IPv4Address("10.10.10.10"))],
        )
        with pytest.raises(ValidationError):
            DNSResourceRecordSetRequest(
                name="foo",
                rrtype=DNSResourceTypeEnum.A,
                a_records=[ARecord(address=IPv4Address("10.10.10.10"))],
                aaaa_records=[AAAARecord(address=IPv6Address("2001:0db8::"))],
            )

    def test_rrtype_matches_records(self) -> None:
        DNSResourceRecordSetRequest(
            name="foo",
            rrtype=DNSResourceTypeEnum.A,
            a_records=[ARecord(address=IPv4Address("10.10.10.10"))],
        )
        with pytest.raises(ValidationException):
            DNSResourceRecordSetRequest(
                name="foo",
                rrtype=DNSResourceTypeEnum.A,
                aaaa_records=[AAAARecord(address=IPv6Address("2001:0db8::"))],
            )

    def to_generic_dns_record(self) -> None:
        req = DNSResourceRecordSetRequest(
            name="foo",
            rrtype=DNSResourceTypeEnum.A,
            a_records=[ARecord(address=IPv4Address("10.10.10.10"))],
        )
        dns_record = req.to_generic_dns_record()
        assert dns_record.name == req.name
        assert dns_record.rrtype == req.rrtype
        assert dns_record.rrdatas == ["10.10.10.10"]
