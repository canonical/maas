#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime

from sqlalchemy import delete, desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.operators import and_, eq, ge, le

from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import RootKeyTable
from maasservicelayer.models.external_auth import RootKey
from maasservicelayer.utils.date import utcnow


class ExternalAuthRepository(Repository):
    GENERATE_INTERVAL = datetime.timedelta(days=1)
    EXPIRY_DURATION = datetime.timedelta(days=1)

    async def create(self) -> RootKey:
        now = utcnow()
        stmt = (
            insert(RootKeyTable)
            .returning(
                RootKeyTable.c.id,
                RootKeyTable.c.created,
                RootKeyTable.c.updated,
                RootKeyTable.c.expiration,
            )
            .values(
                updated=now,
                created=now,
                expiration=now + self.GENERATE_INTERVAL + self.EXPIRY_DURATION,
            )
        )
        result = await self.execute_stmt(stmt)
        root_key = result.one()
        return RootKey(**root_key._asdict())

    async def find_by_id(self, id: int) -> RootKey | None:
        stmt = (
            select("*")
            .select_from(RootKeyTable)
            .where(
                eq(RootKeyTable.c.id, id),
            )
        )
        result = await self.execute_stmt(stmt)
        root_key = result.first()
        if not root_key:
            return None
        return RootKey(**root_key._asdict())

    async def find_best_key(self) -> RootKey | None:
        now = utcnow()
        stmt = (
            select("*")
            .select_from(RootKeyTable)
            .where(
                and_(
                    # Consider the keys that have been generated in the last GENERATE_INTERVAL
                    ge(RootKeyTable.c.created, now - self.GENERATE_INTERVAL),
                    # The key is still valid for at least EXPIRY_DURATION time
                    ge(RootKeyTable.c.expiration, now + self.EXPIRY_DURATION),
                )
            )
            .order_by(desc(RootKeyTable.c.created))
            .limit(1)
        )

        result = (await self.execute_stmt(stmt)).one_or_none()
        return RootKey(**result._asdict()) if result else None

    async def find_expired_keys(self) -> list[RootKey]:
        now = utcnow()
        stmt = (
            select("*")
            .select_from(RootKeyTable)
            .where(le(RootKeyTable.c.expiration, now))
        )

        results = (await self.execute_stmt(stmt)).all()
        return [RootKey(**result._asdict()) for result in results]

    async def delete(self, id: int) -> None:
        stmt = delete(RootKeyTable).where(eq(RootKeyTable.c.id, id))
        await self.execute_stmt(stmt)
