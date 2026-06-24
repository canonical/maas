# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from pydantic import BaseModel


class PowerTypeField(BaseModel):
    name: str
    label: str
    required: bool
    field_type: str
    default: Optional[Any] = None
    choices: Optional[list[tuple[Any, str]]] = None


class PowerTypeResponse(BaseModel):
    driver_type: str
    name: str
    description: str
    fields: list[PowerTypeField]
    chassis: bool
    can_probe: bool
    missing_packages: list[str]
    queryable: bool
    fips_supported: bool
    fips_unsupported_reason: Optional[str] = None


class PowerTypesListResponse(BaseModel):
    items: list[PowerTypeResponse]
