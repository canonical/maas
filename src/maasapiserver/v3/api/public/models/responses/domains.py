# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
from typing import Optional, Self

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
from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.models.dnsresourcerecordsets import GenericDNSRecord
from maasservicelayer.models.domains import Domain


class DomainResponse(HalResponse[BaseHal]):
    kind = "Domain"
    authoritative: bool
    ttl: Optional[int]
    id: int
    name: str
    # TODO: add is_default

    @classmethod
    def from_model(cls, domain: Domain, self_base_hyperlink: str) -> Self:
        return cls(
            authoritative=domain.authoritative,
            ttl=domain.ttl,
            id=domain.id,
            name=domain.name,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{domain.id}"
                )
            ),
        )


class DomainsListResponse(PaginatedResponse[DomainResponse]):
    kind = "DomainsList"


class ARecordResponse(HalResponse[BaseHal]):
    kind = "ARecord"
    ipv4address: IPv4Address

    @classmethod
    def from_model(cls, a_record: ARecord) -> Self:
        return cls(ipv4address=a_record.address)


class AAAARecordResponse(HalResponse[BaseHal]):
    kind = "AAAARecord"
    ipv6address: IPv6Address

    @classmethod
    def from_model(cls, aaaa_record: AAAARecord) -> Self:
        return cls(ipv6address=aaaa_record.address)


class CNAMERecordResponse(HalResponse[BaseHal]):
    kind = "CNAMERecord"
    cname: str

    @classmethod
    def from_model(cls, cname_record: CNAMERecord) -> Self:
        return cls(cname=cname_record.cname)


class MXRecordResponse(HalResponse[BaseHal]):
    kind = "MXRecord"
    exchange: str
    preference: int

    @classmethod
    def from_model(cls, mx_record: MXRecord) -> Self:
        return cls(
            exchange=mx_record.exchange, preference=mx_record.preference
        )


class NSRecordResponse(HalResponse[BaseHal]):
    kind = "NSRecord"
    nsdname: str

    @classmethod
    def from_model(cls, ns_record: NSRecord) -> Self:
        return cls(nsdname=ns_record.nsdname)


class SSHFPRecordResponse(HalResponse[BaseHal]):
    kind = "SSHFPRecord"
    algorithm: int
    fingerprint_type: int
    fingerprint: str

    @classmethod
    def from_model(cls, sshfp_record: SSHFPRecord) -> Self:
        return cls(
            algorithm=sshfp_record.algorithm,
            fingerprint_type=sshfp_record.fingerprint_type,
            fingerprint=sshfp_record.fingerprint,
        )


class SRVRecordResponse(HalResponse[BaseHal]):
    kind = "SRVRecord"
    port: int
    priority: int
    target: str
    weight: int

    @classmethod
    def from_model(cls, srv_record: SRVRecord) -> Self:
        return cls(
            port=srv_record.port,
            priority=srv_record.priority,
            target=srv_record.target,
            weight=srv_record.weight,
        )


class TXTRecordResponse(HalResponse[BaseHal]):
    kind = "TXTRecord"
    data: str

    @classmethod
    def from_model(cls, txt_record: TXTRecord) -> Self:
        return cls(data=txt_record.data)


class DomainResourceRecordSetResponse(HalResponse[BaseHal]):
    kind = "DomainResourceRecordSet"
    name: str
    node_id: Optional[int]
    ttl: Optional[int]
    rrtype: DNSResourceTypeEnum
    a_records: list[ARecordResponse] | None
    aaaa_records: list[AAAARecordResponse] | None
    cname_record: CNAMERecordResponse | None
    mx_records: list[MXRecordResponse] | None
    ns_records: list[NSRecordResponse] | None
    sshfp_records: list[SSHFPRecordResponse] | None
    srv_records: list[SRVRecordResponse] | None
    txt_records: list[TXTRecordResponse] | None

    @classmethod
    def from_model(
        cls,
        dns_record: GenericDNSRecord,
        self_base_hyperlink: str,
    ) -> Self:
        match dns_record.rrtype:
            case DNSResourceTypeEnum.A:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    a_records=[
                        ARecordResponse.from_model(ARecord.from_text(rrdata))
                        for rrdata in dns_record.rrdatas
                    ],
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )
            case DNSResourceTypeEnum.AAAA:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    aaaa_records=[
                        AAAARecordResponse.from_model(
                            AAAARecord.from_text(rrdata)
                        )
                        for rrdata in dns_record.rrdatas
                    ],
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )
            case DNSResourceTypeEnum.CNAME:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    cname_record=CNAMERecordResponse.from_model(
                        CNAMERecord.from_text(dns_record.rrdatas[0])
                    ),
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )
            case DNSResourceTypeEnum.MX:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    mx_records=[
                        MXRecordResponse.from_model(MXRecord.from_text(rrdata))
                        for rrdata in dns_record.rrdatas
                    ],
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )
            case DNSResourceTypeEnum.NS:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    ns_records=[
                        NSRecordResponse.from_model(NSRecord.from_text(rrdata))
                        for rrdata in dns_record.rrdatas
                    ],
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )
            case DNSResourceTypeEnum.SRV:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    srv_records=[
                        SRVRecordResponse.from_model(
                            SRVRecord.from_text(rrdata)
                        )
                        for rrdata in dns_record.rrdatas
                    ],
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )
            case DNSResourceTypeEnum.SSHFP:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    sshfp_records=[
                        SSHFPRecordResponse.from_model(
                            SSHFPRecord.from_text(rrdata)
                        )
                        for rrdata in dns_record.rrdatas
                    ],
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )
            case DNSResourceTypeEnum.TXT:
                return cls(
                    name=dns_record.name,
                    node_id=dns_record.node_id,
                    ttl=dns_record.ttl,
                    rrtype=dns_record.rrtype,
                    txt_records=[
                        TXTRecordResponse.from_model(
                            TXTRecord.from_text(rrdata)
                        )
                        for rrdata in dns_record.rrdatas
                    ],
                    hal_links=BaseHal(
                        self=BaseHref(href=self_base_hyperlink.rstrip("/"))
                    ),
                )


class DomainResourceRecordSetListResponse(
    PaginatedResponse[DomainResourceRecordSetResponse]
):
    kind = "DomainResourceRecordSetList"
