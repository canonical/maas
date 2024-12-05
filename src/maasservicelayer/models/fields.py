# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import _BaseNetwork, IPv4Network, IPv6Network
import re
from typing import Any, Union

from pydantic.networks import NetworkType

from maascommon.fields import MAC_FIELD_RE, normalise_macaddress


class IPv4v6Network(_BaseNetwork):
    """Re-implementation of pydantic's IPvAnyNetwork.

    We need this because pydantic uses `strict=True` by default, but that doesn't
    allow us to set host bits, resulting in all networks having /32.
    """

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, Any]) -> None:
        field_schema.update(type="string", format="ipvanynetwork")

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value: NetworkType) -> Union[IPv4Network, IPv6Network]:
        ip = None
        try:
            ip = IPv4Network(value, strict=False)
        except ValueError:
            pass

        if ip is None:
            try:
                ip = IPv6Network(value, strict=False)
            except ValueError:
                raise ValueError("Value is not a valid IPv4 or IPv6 network.")

        if ip is not None:
            if ip.prefixlen == 0:
                raise ValueError(
                    "The prefix length of the CIDR must be greater than 0."
                )
            return ip


class MacAddress(str):
    def __new__(cls, content):
        content = cls.validate(content)
        return str.__new__(cls, content)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(pattern=MAC_FIELD_RE)

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value: str) -> str:
        match = re.fullmatch(MAC_FIELD_RE, value)
        if match is None:
            raise ValueError("Value is not a valid MAC address.")
        return normalise_macaddress(value)
