#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from itertools import chain
from typing import re

from pydantic import IPvAnyAddress, validator

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maascommon.enums.ipaddress import LeaseAction


class LeaseInfoRequest(NamedBaseModel):
    action: LeaseAction
    ip_family: str
    hostname: str
    mac: str
    ip: IPvAnyAddress
    timestamp: int
    lease_time: int  # seconds

    # Validator to normalize MAC address
    @validator("mac", pre=True)
    def normalize_mac(cls, v):

        MAC_SPLIT_RE = re.compile(r"[-:.]")

        tokens = MAC_SPLIT_RE.split(v.lower())
        match len(tokens):
            case 1:  # no separator
                tokens = re.findall("..", tokens[0])
            case 3:  # each token is two bytes
                tokens = chain(
                    *(re.findall("..", token.zfill(4)) for token in tokens)
                )
            case _:  # single-byte tokens
                tokens = (token.zfill(2) for token in tokens)
        return ":".join(tokens)
