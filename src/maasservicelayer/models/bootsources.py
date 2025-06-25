# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class BootSource(MaasTimestampedBaseModel):
    url: str
    keyring_filename: Optional[str]
    keyring_data: Optional[bytes]
    priority: int
    skip_keyring_verification: bool
