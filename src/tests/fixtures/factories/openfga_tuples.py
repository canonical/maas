# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Any

from maascommon.enums.openfga import OPENFGA_STORE_ID
from maascommon.utils.ulid import generate_ulid
from tests.maasapiserver.fixtures.db import Fixture


async def create_openfga_tuple(
    fixture: Fixture,
    user: str,
    user_type: str,
    relation: str,
    object_type: str,
    object_id: str,
    **extra_details: Any,
) -> dict[str, Any]:
    inserted_at = datetime.now(timezone.utc).astimezone()

    t = {
        "store": OPENFGA_STORE_ID,
        "_user": user,
        "user_type": user_type,
        "relation": relation,
        "object_type": object_type,
        "object_id": object_id,
        "inserted_at": inserted_at,
        "ulid": generate_ulid(),
    }
    t.update(extra_details)

    [created_tuple] = await fixture.create(
        "openfga.tuple",
        [t],
    )

    return created_tuple
