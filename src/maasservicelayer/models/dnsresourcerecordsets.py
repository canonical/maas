#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address
import re
from typing import Any, Optional, Self

from pydantic import BaseModel, Field, root_validator, validator

# starts with a letter, ends with a letter or digit, can contain hyphens, at most 63 chars
LABEL = r"[a-zA-Z]([-a-zA-Z0-9]{0,61}[a-zA-Z0-9]){0,1}"
DOMAIN_NAME_RE = rf"({LABEL}[.])*{LABEL}[.]?"

SRV_LABEL = r"_[a-zA-Z0-9]([-a-zA-Z0-9]{0,61}[a-zA-Z0-9]){0,1}"
SRV_NAME_RE = rf"^{SRV_LABEL}\.{SRV_LABEL}\.{DOMAIN_NAME_RE}$"

SPECIAL_NAMES = ("@", "*")


def validate_domain_name(name: str) -> str:
    if not re.match(rf"^{DOMAIN_NAME_RE}$", name):
        raise ValueError("Invalid domain name.")
    return name


class DNSResourceTypeEnum(StrEnum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    NS = "NS"
    SRV = "SRV"
    SSHFP = "SSHFP"
    TXT = "TXT"


class DNSRecord(BaseModel, ABC):
    @classmethod
    @abstractmethod
    def from_text(cls, rrdata: str) -> Self:
        pass

    @abstractmethod
    def to_text(self) -> str:
        pass


class ARecord(DNSRecord):
    address: IPv4Address

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        return cls(address=IPv4Address(rrdata))

    def to_text(self) -> str:
        return str(self.address)


class AAAARecord(DNSRecord):
    address: IPv6Address

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        return cls(address=IPv6Address(rrdata))

    def to_text(self) -> str:
        return str(self.address)


class CNAMERecord(DNSRecord):
    cname: str

    _validate_cname = validator("cname", allow_reuse=True)(
        validate_domain_name
    )

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        return cls(cname=rrdata.strip())

    def to_text(self) -> str:
        return self.cname


class MXRecord(DNSRecord):
    preference: int = Field(..., ge=0, le=65535)
    exchange: str

    _validate_exchange = validator("exchange", allow_reuse=True)(
        validate_domain_name
    )

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        # don't be too strict on the exchange regex as it's checked later on object creation
        spec = re.compile(r"^(?P<pref>[0-9]+)\s+(?P<exchange>.+)$")
        match = spec.match(rrdata)
        if match is None:
            raise ValueError("Invalid rrdata for MX record.")
        g = match.groupdict()
        return cls(preference=int(g["pref"]), exchange=g["exchange"])

    def to_text(self) -> str:
        return f"{self.preference} {self.exchange}"


class NSRecord(DNSRecord):
    nsdname: str

    _validate_nsdname = validator("nsdname", allow_reuse=True)(
        validate_domain_name
    )

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        return cls(nsdname=rrdata.strip())

    def to_text(self) -> str:
        return self.nsdname


class SRVRecord(DNSRecord):
    priority: int = Field(..., ge=0, le=65535)
    weight: int = Field(..., ge=0, le=65535)
    port: int = Field(..., ge=0, le=65535)
    target: str

    @validator("target")
    def validate_target(cls, target: str) -> str:
        # target can be '.', in which case "the service is decidedly not
        # available at this domain."  Otherwise, it must be a valid name.
        if target != ".":
            return validate_domain_name(target)
        return target

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        spec = re.compile(
            r"^(?P<prio>[0-9]+)\s+(?P<weight>[0-9]+)\s+(?P<port>[0-9]+)\s+"
            r"(?P<target>.*)"
        )
        match = spec.match(rrdata)
        if not match:
            raise ValueError("Invalid rrdata for SRV record.")
        g = match.groupdict()
        return cls(
            priority=int(g["prio"]),
            weight=int(g["weight"]),
            port=int(g["port"]),
            target=g["target"],
        )

    def to_text(self) -> str:
        return f"{self.priority} {self.weight} {self.port} {self.target}"


class SSHFPRecord(DNSRecord):
    algorithm: int = Field(..., ge=0, le=3)
    fingerprint_type: int = Field(..., ge=0, le=2)
    fingerprint: str

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        spec = re.compile(
            r"^(?P<algo>[0-9]+)\s+(?P<fptype>[0-9]+)\s+(?P<fp>[0-9a-fA-F]+)$"
        )
        match = spec.match(rrdata)
        if not match:
            raise ValueError("Invalid rrdata for SSHFP record.")
        g = match.groupdict()
        return cls(
            algorithm=int(g["algo"]),
            fingerprint_type=int(g["fptype"]),
            fingerprint=g["fp"],
        )

    def to_text(self) -> str:
        return f"{self.algorithm} {self.fingerprint_type} {self.fingerprint}"


class TXTRecord(DNSRecord):
    txt_data: str

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        return cls(txt_data=rrdata.strip())

    def to_text(self) -> str:
        return self.txt_data


class DNSResourceRecordSet(BaseModel):
    name: str
    node_id: Optional[int] = None
    ttl: Optional[int] = None
    rrtype: DNSResourceTypeEnum
    a_records: list[ARecord] | None = None
    aaaa_records: list[AAAARecord] | None = None
    cname_records: list[CNAMERecord] | None = None
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
            "cname_records",
            "mx_records",
            "ns_records",
            "sshfp_records",
            "srv_records",
            "txt_records",
        ]
        fields_set_count = sum(
            [1 if values[field] is not None else 0 for field in record_fields]
        )
        if fields_set_count != 1:
            raise ValueError("Only one resource record type must be set.")
        return values

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator
    def ensure_rrtype_matches_records(cls, values: dict[str, Any]):
        error = False
        match values["rrtype"]:
            case DNSResourceTypeEnum.A:
                error = values["a_records"] is None
            case DNSResourceTypeEnum.AAAA:
                error = values["aaaa_records"] is None
            case DNSResourceTypeEnum.CNAME:
                error = values["cname_records"] is None
            case DNSResourceTypeEnum.MX:
                error = values["mx_records"] is None
            case DNSResourceTypeEnum.NS:
                error = values["ns_records"] is None
            case DNSResourceTypeEnum.SRV:
                error = values["srv_records"] is None
            case DNSResourceTypeEnum.SSHFP:
                error = values["sshfp_records"] is None
            case DNSResourceTypeEnum.TXT:
                error = values["txt_records"] is None
        if error:
            raise ValueError(
                "The DNSResourceRecordSet doesn't contain records of the specified type."
            )
        return values

    @classmethod
    def from_rrtype(
        cls,
        name: str,
        node_id: int | None,
        ttl: int | None,
        rrtype: DNSResourceTypeEnum,
        rrdatas: list[str],
    ) -> Self:
        match rrtype:
            case DNSResourceTypeEnum.A:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    a_records=[
                        ARecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
            case DNSResourceTypeEnum.AAAA:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    aaaa_records=[
                        AAAARecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
            case DNSResourceTypeEnum.CNAME:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    cname_records=[
                        CNAMERecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
            case DNSResourceTypeEnum.MX:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    mx_records=[
                        MXRecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
            case DNSResourceTypeEnum.NS:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    ns_records=[
                        NSRecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
            case DNSResourceTypeEnum.SRV:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    srv_records=[
                        SRVRecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
            case DNSResourceTypeEnum.SSHFP:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    sshfp_records=[
                        SSHFPRecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
            case DNSResourceTypeEnum.TXT:
                rrset = cls(
                    name=name,
                    node_id=node_id,
                    ttl=ttl,
                    rrtype=rrtype,
                    txt_records=[
                        TXTRecord.from_text(rrdata) for rrdata in rrdatas
                    ],
                )
        return rrset
