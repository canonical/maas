# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class SshKey(MaasTimestampedBaseModel):
    key: str
    protocol: SshKeysProtocolType | None = None
    auth_id: str | None = None
    user_id: int
