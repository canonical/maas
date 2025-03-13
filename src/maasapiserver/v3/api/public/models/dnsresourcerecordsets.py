#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from ipaddress import IPv4Address, IPv6Address
import re
from typing import Self

from pydantic import BaseModel, Field, validator

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
    data: str

    @classmethod
    def from_text(cls, rrdata: str) -> Self:
        return cls(data=rrdata.strip())

    def to_text(self) -> str:
        return self.data
