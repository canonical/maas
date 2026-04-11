# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Network, IPv6Network
import re
from typing import Annotated, Any, Hashable, TypeVar

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    GetCoreSchemaHandler,
)
from pydantic_core import core_schema, PydanticCustomError

from maascommon.fields import MAC_FIELD_RE, normalise_macaddress

_T = TypeVar("_T", bound=Hashable)


def _validate_unique_list(v: list[_T]) -> list[_T]:
    if len(v) != len(set(v)):
        raise PydanticCustomError("unique_list", "List must be unique")
    return v


# Drop-in replacement for pydantic v1's conlist(unique_items=True).
# Rejects lists with duplicate elements; T must be hashable.
UniqueList = Annotated[
    list[_T],
    AfterValidator(_validate_unique_list),
    Field(json_schema_extra={"uniqueItems": True}),
]


def _validate_ipv4v6_network(value: Any) -> IPv4Network | IPv6Network:
    """Validate an IPv4 or IPv6 network with strict=False.

    Allows host bits in CIDR notation (e.g., 192.168.1.5/24 instead of
    requiring 192.168.1.0/24). Validates that prefix length is greater than 0.
    """
    if isinstance(value, (IPv4Network, IPv6Network)):
        if value.prefixlen == 0:
            raise PydanticCustomError(
                "ip_any_network",
                "The prefix length of the CIDR must be greater than 0.",
            )
        return value

    try:
        network = IPv4Network(value, strict=False)
    except ValueError:
        try:
            network = IPv6Network(value, strict=False)
        except ValueError:
            raise PydanticCustomError(
                "ip_any_network",
                "value is not a valid IPv4 or IPv6 network",
            ) from None

    if network.prefixlen == 0:
        raise PydanticCustomError(
            "ip_any_network",
            "The prefix length of the CIDR must be greater than 0.",
        )

    return network


# Type alias for IPv4 or IPv6 networks with strict=False behavior,
# allowing host bits in CIDR notation (e.g., 192.168.1.5/24).
IPv4v6Network = Annotated[
    IPv4Network | IPv6Network,
    BeforeValidator(_validate_ipv4v6_network),
]


class MacAddress(str):
    def __new__(cls, content):
        content = cls.validate(content)
        return str.__new__(cls, content)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        # Pydantic v2 requires explicit core schema definition for str subclasses.
        # We use core_schema.no_info_after_validator_function instead of
        # Annotated + BeforeValidator because str subclasses with custom __new__
        # cannot be represented through the Annotated approach; they need to define
        # their own validation via __get_pydantic_core_schema__.
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(pattern=MAC_FIELD_RE.pattern),
        )

    @classmethod
    def validate(cls, value: str) -> str:
        match = re.fullmatch(MAC_FIELD_RE, value)
        if match is None:
            raise ValueError("Value is not a valid MAC address.")
        return normalise_macaddress(value)


class PackageRepoUrl(str):
    """
    PPA urls are in the form of `ppa:<user>/<ppa_name>`
    - user: between 3-32 chars, lowercase letters, numbers and hyphens
    - repo: must start with a lowercase letter or number, then lowercase letters,
          numbers, dots, hyphens and pluses.
    OR, they are an http(s) URL.
    """

    PPA_RE = r"^ppa:[a-z0-9\-]{3,32}/[a-z0-9]{1}[a-z0-9\.\-\+]+$"
    URL_RE = r"^https?:\/\/\w[\w\-]+(\.[\w\-]+)+(\/([\w\-_%.#?=&+])+)*\/?$"
    COMBINED_RE = re.compile(rf"{PPA_RE}|{URL_RE}")

    def __new__(cls, content):
        content = cls.validate(content)
        return str.__new__(cls, content)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        # Pydantic v2 requires explicit core schema definition for str subclasses.
        # We use core_schema.no_info_after_validator_function instead of
        # Annotated + BeforeValidator because str subclasses with custom __new__
        # cannot be represented through the Annotated approach; they need to define
        # their own validation via __get_pydantic_core_schema__.
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(pattern=cls.COMBINED_RE.pattern),
        )

    @classmethod
    def validate(cls, value: str) -> str:
        match = re.fullmatch(cls.COMBINED_RE, value)
        if match is None:
            raise ValueError("Value is not a valid PPA URL.")
        return value
