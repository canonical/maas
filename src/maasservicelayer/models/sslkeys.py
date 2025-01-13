#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import MaasTimestampedBaseModel


class SSLKey(MaasTimestampedBaseModel):
    key: str
    user_id: int
