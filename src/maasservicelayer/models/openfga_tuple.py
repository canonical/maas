# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel

from maasservicelayer.models.base import generate_builder


@generate_builder()
class OpenFGATuple(BaseModel):
    object_type: str
    object_id: str
    relation: str
    user: str
    user_type: str
