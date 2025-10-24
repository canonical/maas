# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from pydantic import BaseModel

from maasservicelayer.models.base import generate_builder
from maasservicelayer.simplestreams.models import SimpleStreamsManifest


@generate_builder()
class ImageManifest(BaseModel):
    boot_source_id: int
    manifest: SimpleStreamsManifest
    last_update: datetime
