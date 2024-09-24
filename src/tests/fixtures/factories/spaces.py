# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Factories for the Spaces"""

from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.spaces import Space
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_space_entry(
    fixture: Fixture, **extra_details: Any
) -> Space:
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)
    space = {
        "name": "my_space",
        "description": "space description",
        "created": created_at,
        "updated": updated_at,
    }
    space.update(extra_details)
    [created_space] = await fixture.create("maasserver_space", [space])
    return Space(**created_space)
