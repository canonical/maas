#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


from collections.abc import Sequence
from typing import Optional

from pydantic import BaseModel, Field

from maasservicelayer.auth.macaroons.models.base import Resource


class UpdateResourcesRequest(BaseModel):
    updates: Optional[Sequence[Resource]]
    removals: Optional[Sequence[int]]
    last_sync_id: Optional[str] = Field(serialization_alias="last-sync-id")
