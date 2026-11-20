#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.api_tokens import (
    ApiTokenClauseFactory,
    ApiTokenOrderByClauses,
    ApiTokenRepository,
)
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.token import create_test_api_token
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture


class TestApiTokenRepository:
    async def test_list_hides_revoked_and_orders_by_last_used(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        now = utcnow()
        never_used = await create_test_api_token(
            fixture, public_id="a" * 16, user_id=user.id
        )
        recently_used = await create_test_api_token(
            fixture, public_id="b" * 16, user_id=user.id, last_used_at=now
        )
        await create_test_api_token(
            fixture, public_id="c" * 16, user_id=user.id, revoked_at=now
        )
        repository = ApiTokenRepository(Context(connection=db_connection))

        result = await repository.list(
            page=1,
            size=10,
            query=QuerySpec(
                where=ApiTokenClauseFactory.and_clauses(
                    [
                        ApiTokenClauseFactory.with_user_id(user.id),
                        ApiTokenClauseFactory.not_revoked(),
                    ]
                ),
                order_by=ApiTokenOrderByClauses.last_used_at_desc(),
            ),
        )

        assert [token.id for token in result.items] == [
            recently_used.id,
            never_used.id,
        ]
