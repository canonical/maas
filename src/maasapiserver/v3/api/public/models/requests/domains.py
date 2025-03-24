# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, root_validator

from maasapiserver.v3.api.public.models.dnsresourcerecordsets import (
    AAAARecord,
    ARecord,
    CNAMERecord,
    MXRecord,
    NSRecord,
    SPECIAL_NAMES,
    SRV_NAME_RE,
    SRVRecord,
    SSHFPRecord,
    TXTRecord,
    validate_domain_name,
)
from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.builders.domains import DomainBuilder
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.dnsresourcerecordsets import GenericDNSRecord


class DomainRequest(NamedBaseModel):
    name: str = Field(description="Name of the domain.")
    authoritative: bool = Field(
        description="Class type of the domain", default=True
    )
    ttl: Optional[int] = Field(
        description="TTL for the domain.", default=None, ge=1, le=604800
    )

    def to_builder(self) -> DomainBuilder:
        return DomainBuilder(
            name=self.name, authoritative=self.authoritative, ttl=self.ttl
        )


class DNSResourceRecordSetRequest(BaseModel):
    name: str
    ttl: Optional[int] = None
    rrtype: DNSResourceTypeEnum
    a_records: list[ARecord] | None = None
    aaaa_records: list[AAAARecord] | None = None
    cname_record: CNAMERecord | None = None
    mx_records: list[MXRecord] | None = None
    ns_records: list[NSRecord] | None = None
    sshfp_records: list[SSHFPRecord] | None = None
    srv_records: list[SRVRecord] | None = None
    txt_records: list[TXTRecord] | None = None

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator
    def validate_domain_name_based_on_type(cls, values: dict[str, Any]):
        if values["name"] not in SPECIAL_NAMES:
            if values["rrtype"] == DNSResourceTypeEnum.SRV:
                if not re.match(SRV_NAME_RE, values["name"]):
                    raise ValueError("Invalid SRV domain name.")
            else:
                validate_domain_name(values["name"])
        return values

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator
    def ensure_only_one_record_set(cls, values: dict[str, Any]):
        record_fields = [
            "a_records",
            "aaaa_records",
            "cname_record",
            "mx_records",
            "ns_records",
            "sshfp_records",
            "srv_records",
            "txt_records",
        ]
        fields_set_count = sum(
            [
                1 if values.get(field, None) is not None else 0
                for field in record_fields
            ]
        )
        if fields_set_count != 1:
            raise ValueError("Only one resource record type must be set.")
        return values

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator
    def ensure_rrtype_matches_records(cls, values: dict[str, Any]):
        error = False
        field = None
        match values["rrtype"]:
            case DNSResourceTypeEnum.A:
                field = "a_records"
            case DNSResourceTypeEnum.AAAA:
                field = "aaaa_records"
            case DNSResourceTypeEnum.CNAME:
                field = "cname_record"
            case DNSResourceTypeEnum.MX:
                field = "mx_records"
            case DNSResourceTypeEnum.NS:
                field = "ns_records"
            case DNSResourceTypeEnum.SRV:
                field = "srv_records"
            case DNSResourceTypeEnum.SSHFP:
                field = "sshfp_records"
            case DNSResourceTypeEnum.TXT:
                field = "txt_records"
        if field is not None:
            error = values.get(field, None) is None
            if error:
                raise ValidationException.build_for_field(
                    field=field,
                    message="Missing required field for the rrtype specified",
                )
        return values

    def to_generic_dns_record(self) -> GenericDNSRecord:
        match self.rrtype:
            case DNSResourceTypeEnum.A:
                assert self.a_records is not None
                rrdatas = [r.to_text() for r in self.a_records]
            case DNSResourceTypeEnum.AAAA:
                assert self.aaaa_records is not None
                rrdatas = [r.to_text() for r in self.aaaa_records]
            case DNSResourceTypeEnum.CNAME:
                assert self.cname_record is not None
                rrdatas = [self.cname_record.to_text()]
            case DNSResourceTypeEnum.MX:
                assert self.mx_records is not None
                rrdatas = [r.to_text() for r in self.mx_records]
            case DNSResourceTypeEnum.NS:
                assert self.ns_records is not None
                rrdatas = [r.to_text() for r in self.ns_records]
            case DNSResourceTypeEnum.SRV:
                assert self.srv_records is not None
                rrdatas = [r.to_text() for r in self.srv_records]
            case DNSResourceTypeEnum.SSHFP:
                assert self.sshfp_records is not None
                rrdatas = [r.to_text() for r in self.sshfp_records]
            case DNSResourceTypeEnum.TXT:
                assert self.txt_records is not None
                rrdatas = [r.to_text() for r in self.txt_records]

        return GenericDNSRecord(
            name=self.name, ttl=self.ttl, rrtype=self.rrtype, rrdatas=rrdatas
        )
