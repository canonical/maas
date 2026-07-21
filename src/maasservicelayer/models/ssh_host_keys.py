# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class TrustedSshHostKey(MaasTimestampedBaseModel):
    host: str
    key_type: str
    public_key: str
    label: Optional[str] = None
