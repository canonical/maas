# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from pydantic import BaseModel

from maascommon.openfga.base import OpenFGAEntitlementResourceType
from maasservicelayer.models.base import generate_builder


@dataclass(frozen=True)
class EntitlementDeleteSpec:
    entitlement: str
    resource_type: OpenFGAEntitlementResourceType
    resource_id: int


@generate_builder()
class OpenFGATuple(BaseModel):
    object_type: str
    object_id: str
    relation: str
    user: str
    user_type: str
