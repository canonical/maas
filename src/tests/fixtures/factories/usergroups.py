# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.usergroups import UserGroup
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_usergroup(
    fixture: Fixture, **extra_details: Any
) -> UserGroup:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    usergroup = {
        "name": "my_group",
        "description": "",
        "created": created_at,
        "updated": updated_at,
    }
    usergroup.update(extra_details)
    [created_group] = await fixture.create(
        "maasserver_usergroup",
        [usergroup],
    )
    return UserGroup(**created_group)
