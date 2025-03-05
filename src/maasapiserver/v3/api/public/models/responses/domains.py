# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
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
)
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
        return cls(data=txt_record.txt_data)


class DomainResourceRecordSetResponse(HalResponse[BaseHal]):
    kind = "DomainResourceRecordSet"
    name: str
    node_id: Optional[int]
    ttl: Optional[int]
    rrtype: DNSResourceTypeEnum
    a_records: list[ARecordResponse] | None
    aaaa_records: list[AAAARecordResponse] | None
    cname_records: list[CNAMERecordResponse] | None
    mx_records: list[MXRecordResponse] | None
    ns_records: list[NSRecordResponse] | None
    sshfp_records: list[SSHFPRecordResponse] | None
    srv_records: list[SRVRecordResponse] | None
    txt_records: list[TXTRecordResponse] | None

    @classmethod
    def from_model(
        cls,
        rrset: DNSResourceRecordSet,
        self_base_hyperlink: str,
    ) -> Self:
        return cls(
            name=rrset.name,
            node_id=rrset.node_id,
            ttl=rrset.node_id,
            rrtype=rrset.rrtype,
            a_records=[ARecordResponse.from_model(r) for r in rrset.a_records]
            if rrset.a_records is not None
            else None,
            aaaa_records=[
                AAAARecordResponse.from_model(r) for r in rrset.aaaa_records
            ]
            if rrset.aaaa_records is not None
            else None,
            cname_records=[
                CNAMERecordResponse.from_model(r) for r in rrset.cname_records
            ]
            if rrset.cname_records is not None
            else None,
            mx_records=[
                MXRecordResponse.from_model(r) for r in rrset.mx_records
            ]
            if rrset.mx_records is not None
            else None,
            ns_records=[
                NSRecordResponse.from_model(r) for r in rrset.ns_records
            ]
            if rrset.ns_records is not None
            else None,
            sshfp_records=[
                SSHFPRecordResponse.from_model(r) for r in rrset.sshfp_records
            ]
            if rrset.sshfp_records is not None
            else None,
            srv_records=[
                SRVRecordResponse.from_model(r) for r in rrset.srv_records
            ]
            if rrset.srv_records is not None
            else None,
            txt_records=[
                TXTRecordResponse.from_model(r) for r in rrset.txt_records
            ]
            if rrset.txt_records is not None
            else None,
            hal_links=BaseHal(
                self=BaseHref(href=f"{self_base_hyperlink.rstrip('/')}")
            ),
        )


class DomainResourceRecordSetListResponse(
    PaginatedResponse[DomainResourceRecordSetResponse]
):
    kind = "DomainResourceRecordSetList"
