# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import _BaseNetwork, IPv4Network, IPv6Network
import re
from typing import Any, Union

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from maascommon.fields import MAC_FIELD_RE, normalise_macaddress

# Type alias for network validation input
NetworkType = Union[str, IPv4Network, IPv6Network]


class IPv4v6Network(_BaseNetwork):
    """Re-implementation of pydantic's IPvAnyNetwork.

    We need this because pydantic uses `strict=True` by default, but that doesn't
    allow us to set host bits, resulting in all networks having /32.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.union_schema(
                [
                    core_schema.is_instance_schema(IPv4Network),
                    core_schema.is_instance_schema(IPv6Network),
                    core_schema.str_schema(),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: str(v),
                return_schema=core_schema.str_schema(),
            ),
        )

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
                raise ValueError("Value is not a valid IPv4 or IPv6 network.")  # noqa: B904

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
