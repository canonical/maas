# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from fastapi import Query
from pydantic import BaseModel, Field, IPvAnyAddress, root_validator

from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.fields import MacAddress


class DiscoveriesIPAndMacFiltersParams(BaseModel):
    ip: Optional[IPvAnyAddress] = Field(
        Query(default=None, description="Delete discoveries with this IP.")
    )
    mac: Optional[MacAddress] = Field(
        Query(default=None, description="Delete discoveries with this MAC.")
    )

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator
    def validate_model(cls, values: dict[str, Any]):
        if bool(values["ip"]) ^ bool(values["mac"]):
            missing_field = "ip" if values["ip"] is None else "mac"
            message = f"Missing '{missing_field}' query parameter. You must specify both IP and MAC to delete a specific neighbour."
            raise ValidationException.build_for_field(missing_field, message)
        return values
