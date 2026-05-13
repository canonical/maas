# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Any

from pydantic import Field

from maasservicelayer.models.base import ResourceBuilder, UNSET, Unset


class PowerDriverBuilder(ResourceBuilder):
    """Builder for PowerDriver model."""

    created: datetime | Unset = Field(default=UNSET)
    updated: datetime | Unset = Field(default=UNSET)
    rack_system_id: str | Unset = Field(default=UNSET)
    driver_name: str | Unset = Field(default=UNSET)
    driver_version: str | Unset = Field(default=UNSET)
    schema: dict[str, Any] | Unset = Field(default=UNSET)
