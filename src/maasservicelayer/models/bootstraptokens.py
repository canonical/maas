# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import datetime

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class BootstrapToken(MaasTimestampedBaseModel):
    expires_at: datetime.datetime
    secret: str
    rack_id: int
