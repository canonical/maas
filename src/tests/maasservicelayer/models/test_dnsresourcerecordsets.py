#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from pydantic import ValidationError
import pytest

from maasservicelayer.models.dnsresourcerecordsets import (
    AAAARecord,
    ARecord,
    CNAMERecord,
    DNSResourceRecordSet,
    DNSResourceTypeEnum,
    MXRecord,
    NSRecord,
    SRVRecord,
    SSHFPRecord,
    TXTRecord,
    validate_domain_name,
)


@pytest.mark.parametrize(
    "name, should_raise",
    [
        # length checks
        ("", True),  # too short
        ("a", False),
        ("a" * 63, False),
        ("a" * 64, True),  # part too long
        # valid
        ("example", False),
        ("EXAMPLE", False),
        ("subdomain.example", False),
        ("domain-with-hyphens", False),
        # doesn't start with a letter
        ("0.example", True),
        ("-example", True),
        (".example", True),
        # only letters, numbers and hyphens
        ("invalid_chars", True),
        ("!test", True),
        ("comma,", True),
    ],
)
def test_validate_domain_name(name, should_raise: bool):
    if should_raise:
        with pytest.raises(ValueError):
            validate_domain_name(name)
    else:
        validate_domain_name(name)


class TestARecord:
    @pytest.mark.parametrize(
        "rrdata, should_raise",
        [("10.10.10.10", False)],
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                ARecord.from_text(rrdata)
        else:
            ARecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = ARecord(address=IPv4Address("10.10.10.10"))
        assert record.to_text() == "10.10.10.10"


class TestAAAARecord:
    @pytest.mark.parametrize(
        "rrdata, should_raise",
        [
            ("2001:0db8:0020:000a:0000:0000:0000:0004", False),
            ("2001:0db8::", False),
        ],
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                AAAARecord.from_text(rrdata)
        else:
            AAAARecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = AAAARecord(address=IPv6Address("2001:db8::"))
        assert record.to_text() == "2001:db8::"


class TestCNAMERecord:
    # cname validation already tested in `test_validate_domain_name`
    @pytest.mark.parametrize(
        "rrdata, should_raise", [(" cname  ", False), ("cname", False)]
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                CNAMERecord.from_text(rrdata)
        else:
            CNAMERecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = CNAMERecord(cname="cname")
        assert record.to_text() == "cname"


class TestMXRecord:
    # exchange validation already tested in `test_validate_domain_name`
    @pytest.mark.parametrize(
        "rrdata, should_raise",
        [
            ("0 mailhost1.example.com", False),
            ("10 mailhost1.example.com", False),
            ("65535 mailhost1.example.com", False),
            ("65536 mailhost1.example.com", True),
            ("-1 mailhost1.example.com", True),
            ("foo mailhost1.example.com", True),
        ],
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValueError):
                MXRecord.from_text(rrdata)
        else:
            MXRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = MXRecord(preference=0, exchange="mailhost1.example.com")
        assert record.to_text() == "0 mailhost1.example.com"


class TestNSRecord:
    # nsdname validation already tested in `test_validate_domain_name`
    @pytest.mark.parametrize(
        "rrdata, should_raise", [(" nsdname  ", False), ("nsdname", False)]
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                NSRecord.from_text(rrdata)
        else:
            NSRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = NSRecord(nsdname="nsdname")
        assert record.to_text() == "nsdname"


class TestSRVRecord:
    # target validation already tested in `test_validate_domain_name`
    # format: priority weight port target
    # target can also be "."
    @pytest.mark.parametrize(
        "rrdata, should_raise",
        [
            ("0 0 0 .", False),
            ("65535 65535 65535 .", False),
            # invalid priority
            ("65536 0 0 .", True),
            ("foo 0 0 .", True),
            ("- 0 0 .", True),
            # invalid weight
            ("0 65536 0 .", True),
            ("0 foo 0 .", True),
            ("0 - 0 .", True),
            # invalid port
            ("0 0 65536 .", True),
            ("0 0 foo .", True),
            ("0 0 - .", True),
            # invalid number of arguments
            ("0 0 example.com", True),
            ("0 0 0", True),
        ],
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValueError):
                SRVRecord.from_text(rrdata)
        else:
            SRVRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = SRVRecord(
            priority=10, weight=5, port=5223, target="server.example.com"
        )
        assert record.to_text() == "10 5 5223 server.example.com"


class TestSSHFPRecord:
    # target validation already tested in `test_validate_domain_name`
    # format: algorithm fingerprint_type fingerprint
    @pytest.mark.parametrize(
        "rrdata, should_raise",
        [
            ("0 0 123456789abcdef67890123456789abcdef67890", False),
            ("1 1 123456789abcdef67890123456789abcdef67890", False),
            ("2 2 123456789abcdef67890123456789abcdef67890", False),
            ("3 2 123456789abcdef67890123456789abcdef67890", False),
            # invalid algorithm
            ("4 2 123456789abcdef67890123456789abcdef67890", True),
            ("-1 2 123456789abcdef67890123456789abcdef67890", True),
            # invalid fingerprint_type
            ("0 3 123456789abcdef67890123456789abcdef67890", True),
            ("1 -1 123456789abcdef67890123456789abcdef67890", True),
            # invalid chars in fingerprint (non hex)
            ("0 0 l", True),
            ("0 0 !", True),
            # invalid number of arguments
            ("0", True),
            ("0 0", True),
            ("0 0 123456789abcdef67890123456789abcdef67890 foo", True),
        ],
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValueError):
                SSHFPRecord.from_text(rrdata)
        else:
            SSHFPRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = SSHFPRecord(
            algorithm=0,
            fingerprint_type=0,
            fingerprint="123456789abcdef67890123456789abcdef67890",
        )
        assert (
            record.to_text() == "0 0 123456789abcdef67890123456789abcdef67890"
        )


class TestTXTRecord:
    def test_from_text(self) -> None:
        txt = TXTRecord.from_text("Example data for txt record")
        assert txt.txt_data == "Example data for txt record"

    def test_to_text(self) -> None:
        txt = TXTRecord(txt_data="Example data for txt record")
        assert txt.to_text() == "Example data for txt record"


class TestDNSResourceRecordSet:
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
                DNSResourceRecordSet(
                    name=name,
                    rrtype=DNSResourceTypeEnum.SRV,
                    srv_records=[record],
                )
        else:
            DNSResourceRecordSet(
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
                DNSResourceRecordSet(
                    name=name, rrtype=DNSResourceTypeEnum.A, a_records=[record]
                )
        else:
            DNSResourceRecordSet(
                name=name, rrtype=DNSResourceTypeEnum.A, a_records=[record]
            )

    def test_ensure_only_one_record_set(self) -> None:
        DNSResourceRecordSet(
            name="foo",
            rrtype=DNSResourceTypeEnum.A,
            a_records=[ARecord(address=IPv4Address("10.10.10.10"))],
        )
        with pytest.raises(ValidationError):
            DNSResourceRecordSet(
                name="foo",
                rrtype=DNSResourceTypeEnum.A,
                a_records=[ARecord(address=IPv4Address("10.10.10.10"))],
                aaaa_records=[AAAARecord(address=IPv6Address("2001:0db8::"))],
            )

    def test_rrtype_matches_records(self) -> None:
        DNSResourceRecordSet(
            name="foo",
            rrtype=DNSResourceTypeEnum.A,
            a_records=[ARecord(address=IPv4Address("10.10.10.10"))],
        )
        with pytest.raises(ValidationError):
            DNSResourceRecordSet(
                name="foo",
                rrtype=DNSResourceTypeEnum.A,
                aaaa_records=[AAAARecord(address=IPv6Address("2001:0db8::"))],
            )
