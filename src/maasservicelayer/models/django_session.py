# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from pydantic import BaseModel

from maasservicelayer.models.base import generate_builder


@generate_builder()
class DjangoSession(BaseModel):
    session_key: str
    session_data: str
    expire_date: datetime
