# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.models.base import MaasTimestampedBaseModel


class SshKey(MaasTimestampedBaseModel):
    key: str
    protocol: Optional[SshKeysProtocolType] = None
    auth_id: Optional[str] = None
    user_id: int
