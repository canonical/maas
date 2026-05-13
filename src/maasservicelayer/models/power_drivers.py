# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel, ConfigDict

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


class DriverAction(BaseModel):
    """A power action supported by a driver."""

    name: str


class DriverSetting(BaseModel):
    """A configuration setting for a driver."""

    name: str
    label: str
    field_type: str
    required: bool = False
    secret: bool = False


class DriverCapabilities(BaseModel):
    """Capabilities of a power driver."""

    queryable: bool = False
    chassis: bool = False
    can_probe: bool = False
    can_set_boot_order: bool = False


class IpExtractor(BaseModel):
    """IP address extraction configuration."""

    field_name: str
    pattern: str


class DriverSchema(BaseModel):
    """Validation schema for power driver metadata."""

    name: str
    description: str
    version: str
    actions: list[DriverAction]
    settings: list[DriverSetting]
    capabilities: DriverCapabilities
    ip_extractor: IpExtractor | None = None


@generate_builder()
class PowerDriver(MaasTimestampedBaseModel):
    """Domain model for a rack-registered power driver."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    rack_system_id: str
    driver_name: str
    driver_version: str
    schema: dict[str, Any]  # noqa: E501  # Deliberately named 'schema' to match DB column
