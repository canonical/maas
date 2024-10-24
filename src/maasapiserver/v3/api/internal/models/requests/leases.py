#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from itertools import chain
import re

from pydantic import BaseModel, IPvAnyAddress, validator

from maascommon.enums.ipaddress import LeaseAction


class LeaseInfoRequest(BaseModel):
    action: LeaseAction
    ip_family: str
    hostname: str
    mac: str
    ip: IPvAnyAddress
    timestamp: int
    lease_time: int  # seconds

    # Validator to normalize MAC address
    @validator("mac", pre=True)
    def normalize_mac(cls, v: str) -> str:
        MAC_SPLIT_RE = re.compile(r"[-:.]")
        VALID_MAC_RE = re.compile(r"^[0-9a-fA-F:. -]+$")

        if not VALID_MAC_RE.match(v):
            raise ValueError(f"Invalid characters in MAC address {v}.")

        tokens = MAC_SPLIT_RE.split(v.lower())
        match len(tokens):
            case 1:  # no separator
                tokens = re.findall("..", tokens[0])
            case 3:  # each token is two bytes (when using dots)
                tokens = chain(
                    *(re.findall("..", token.zfill(4)) for token in tokens)
                )
            case _:  # single-byte tokens (for colons, hyphens)
                tokens = (token.zfill(2) for token in tokens)

        normalized_mac = ":".join(tokens)
        if (
            len(normalized_mac) != 17
        ):  # MAC address must have exactly 17 characters
            raise ValueError(f"Invalid MAC address length {normalized_mac}.")

        return normalized_mac
