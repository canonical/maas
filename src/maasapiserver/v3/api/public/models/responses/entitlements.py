# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import BaseModel

from maasservicelayer.models.openfga_tuple import OpenFGATuple


class EntitlementResponse(BaseModel):
    kind = "Entitlement"
    resource_type: str
    resource_id: int
    entitlement: str

    @classmethod
    def from_model(cls, tuple_: OpenFGATuple) -> Self:
        return cls(
            resource_type=tuple_.object_type,
            resource_id=int(tuple_.object_id),
            entitlement=tuple_.relation,
        )
