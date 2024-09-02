#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from maasservicelayer.models.base import MaasTimestampedBaseModel


class RootKey(MaasTimestampedBaseModel):
    expiration: datetime
