# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Network, IPv6Network
import re
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic.networks import IPvAnyNetwork
from pydantic_core import core_schema, PydanticCustomError

from maascommon.fields import MAC_FIELD_RE, normalise_macaddress


class IPv4v6Network(IPvAnyNetwork):
    """IPv4 or IPv6 network validator with strict=False.

    Inherits from pydantic's IPvAnyNetwork but allows host bits in CIDR
    notation (e.g., 192.168.1.5/24 instead of requiring 192.168.1.0/24).
    Validates that prefix length is greater than 0.
    """

    def __new__(cls, value):
        """Validate an IPv4 or IPv6 network with strict=False."""
        try:
            network = IPv4Network(value, strict=False)
        except ValueError:
            try:
                network = IPv6Network(value, strict=False)
            except ValueError:
                raise PydanticCustomError(
                    "ip_any_network",
                    "value is not a valid IPv4 or IPv6 network",
                )

        if network.prefixlen == 0:
            raise PydanticCustomError(
                "ip_any_network",
                "The prefix length of the CIDR must be greater than 0.",
            )

        return network


class MacAddress(str):
    def __new__(cls, content):
        content = cls.validate(content)
        return str.__new__(cls, content)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
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
