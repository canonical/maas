#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


from collections.abc import Sequence

from pydantic import BaseModel, Field

from maasservicelayer.auth.macaroons.models.base import Resource


class UpdateResourcesRequest(BaseModel):
    updates: Sequence[Resource] | None = None
    removals: Sequence[int] | None = None
    last_sync_id: str | None = Field(default=None, serialization_alias="last-sync-id")
