#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Notification(MaasTimestampedBaseModel):
    ident: str
    users: bool
    admins: bool
    message: str
    context: dict[str, Any]
    user_id: Optional[int]
    category: str
    dismissable: bool
