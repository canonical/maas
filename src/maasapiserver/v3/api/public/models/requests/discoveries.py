# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from fastapi import Query
from pydantic import BaseModel, Field, IPvAnyAddress, model_validator

from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.fields import MacAddress


class DiscoveriesIPAndMacFiltersParams(BaseModel):
    ip: IPvAnyAddress | None = Field(
        Query(default=None, description="Delete discoveries with this IP.")
    )
    mac: MacAddress | None = Field(
        Query(default=None, description="Delete discoveries with this MAC.")
    )

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        if bool(self.ip) ^ bool(self.mac):
            missing_field = "ip" if self.ip is None else "mac"
            message = f"Missing '{missing_field}' query parameter. You must specify both IP and MAC to delete a specific neighbour."
            raise ValidationException.build_for_field(
                missing_field, message, location="query"
            )
        return self
