# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.models.tokens import Token
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_user_token(
    fixture: Fixture, user_id: int, consumer_id: int, **extra_details: Any
) -> Token:
    token = {
        "key": "CtE9Cmy4asnRBtJvxQ",
        "secret": "DNPJDVa87vEesHE8sQ722yP6JJKnrem2",
        "verifier": "",
        "token_type": 2,
        "timestamp": 1725122700,
        "is_approved": True,
        "callback_confirmed": False,
        "consumer_id": consumer_id,
        "user_id": user_id,
    }

    [created_token] = await fixture.create("piston3_token", [token])
    return Token(**created_token)
