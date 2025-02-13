#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from pydantic import ValidationError
import pytest

from maasservicelayer.models.dnsresourcerecordsets import (
    AaaaDnsRecord,
    ADnsRecord,
    CnameDnsRecord,
    DnsResourceRecordSet,
    DnsResourceTypeEnum,
    MxDnsRecord,
    NsDnsRecord,
    SrvDnsRecord,
    SshfpDnsRecord,
    TxtDnsRecord,
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


class TestADnsRecord:
    @pytest.mark.parametrize(
        "rrdata, should_raise",
        [("  10.10.10.10 ", False), ("10.10.10.10", False)],
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                ADnsRecord.from_text(rrdata)
        else:
            ADnsRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = ADnsRecord(address=IPv4Address("10.10.10.10"))
        assert record.to_text() == "10.10.10.10"


class TestAAAADnsRecord:
    @pytest.mark.parametrize(
        "rrdata, should_raise",
        [
            ("2001:0db8:0020:000a:0000:0000:0000:0004", False),
            ("2001:0db8::", False),
            ("  2001:0db8::  ", False),
        ],
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                AaaaDnsRecord.from_text(rrdata)
        else:
            AaaaDnsRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = AaaaDnsRecord(address=IPv6Address("2001:db8::"))
        assert record.to_text() == "2001:db8::"


class TestCnameDnsRecord:
    # cname validation already tested in `test_validate_domain_name`
    @pytest.mark.parametrize(
        "rrdata, should_raise", [(" cname  ", False), ("cname", False)]
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                CnameDnsRecord.from_text(rrdata)
        else:
            CnameDnsRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = CnameDnsRecord(cname="cname")
        assert record.to_text() == "cname"


class TestMxDnsRecord:
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
                MxDnsRecord.from_text(rrdata)
        else:
            MxDnsRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = MxDnsRecord(preference=0, exchange="mailhost1.example.com")
        assert record.to_text() == "0 mailhost1.example.com"


class TestNsDnsRecord:
    # nsdname validation already tested in `test_validate_domain_name`
    @pytest.mark.parametrize(
        "rrdata, should_raise", [(" nsdname  ", False), ("nsdname", False)]
    )
    def test_from_text(self, rrdata: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationError):
                NsDnsRecord.from_text(rrdata)
        else:
            NsDnsRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = NsDnsRecord(nsdname="nsdname")
        assert record.to_text() == "nsdname"


class TestSrvDnsRecord:
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
                SrvDnsRecord.from_text(rrdata)
        else:
            SrvDnsRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = SrvDnsRecord(
            priority=10, weight=5, port=5223, target="server.example.com"
        )
        assert record.to_text() == "10 5 5223 server.example.com"


class TestSshfpDnsRecord:
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
                SshfpDnsRecord.from_text(rrdata)
        else:
            SshfpDnsRecord.from_text(rrdata)

    def test_to_text(self) -> None:
        record = SshfpDnsRecord(
            algorithm=0,
            fingerprint_type=0,
            fingerprint="123456789abcdef67890123456789abcdef67890",
        )
        assert (
            record.to_text() == "0 0 123456789abcdef67890123456789abcdef67890"
        )


class TestTxtDnsRecord:
    def test_from_text(self) -> None:
        txt = TxtDnsRecord.from_text("Example data for txt record")
        assert txt.txt_data == "Example data for txt record"

    def test_to_text(self) -> None:
        txt = TxtDnsRecord(txt_data="Example data for txt record")
        assert txt.to_text() == "Example data for txt record"


class TestDnsResourceRecordSet:
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
        record = SrvDnsRecord(
            priority=10, weight=5, port=5223, target="server.example.com"
        )
        if should_raise:
            with pytest.raises(ValidationError):
                DnsResourceRecordSet(
                    name=name,
                    rrtype=DnsResourceTypeEnum.SRV,
                    srv_records=[record],
                )
        else:
            DnsResourceRecordSet(
                name=name, rrtype=DnsResourceTypeEnum.SRV, srv_records=[record]
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
        record = ADnsRecord(address=IPv4Address("10.10.10.10"))
        if should_raise:
            with pytest.raises(ValidationError):
                DnsResourceRecordSet(
                    name=name, rrtype=DnsResourceTypeEnum.A, a_records=[record]
                )
        else:
            DnsResourceRecordSet(
                name=name, rrtype=DnsResourceTypeEnum.A, a_records=[record]
            )

    def test_ensure_only_one_record_set(self) -> None:
        DnsResourceRecordSet(
            name="foo",
            rrtype=DnsResourceTypeEnum.A,
            a_records=[ADnsRecord(address=IPv4Address("10.10.10.10"))],
        )
        with pytest.raises(ValidationError):
            DnsResourceRecordSet(
                name="foo",
                rrtype=DnsResourceTypeEnum.A,
                a_records=[ADnsRecord(address=IPv4Address("10.10.10.10"))],
                aaaa_records=[
                    AaaaDnsRecord(address=IPv6Address("2001:0db8::"))
                ],
            )

    def test_rrtype_matches_records(self) -> None:
        DnsResourceRecordSet(
            name="foo",
            rrtype=DnsResourceTypeEnum.A,
            a_records=[ADnsRecord(address=IPv4Address("10.10.10.10"))],
        )
        with pytest.raises(ValidationError):
            DnsResourceRecordSet(
                name="foo",
                rrtype=DnsResourceTypeEnum.A,
                aaaa_records=[
                    AaaaDnsRecord(address=IPv6Address("2001:0db8::"))
                ],
            )
