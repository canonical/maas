# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.models.consumers import Consumer
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_user_consumer(
    fixture: Fixture, user_id: int, **extra_details: Any
) -> Consumer:
    consumer = {
        "name": "myconsumername",
        "description": "myconsumerdescription",
        "key": "cqJF8TCX9gZw8SZpNr",
        "secret": "",
        "status": "accepted",
        "user_id": user_id,
    }

    consumer.update(extra_details)
    [created_consumer] = await fixture.create("piston3_consumer", [consumer])
    return Consumer(**created_consumer)
