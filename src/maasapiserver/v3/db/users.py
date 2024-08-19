from datetime import datetime

from django.core import signing
from sqlalchemy import select
from sqlalchemy.sql.operators import and_, eq, gt

from maasapiserver.v3.db.base import BaseRepository, CreateOrUpdateResource
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.users import User, UserProfile
from maasservicelayer.db.filters import FilterQuery
from maasservicelayer.db.tables import (
    SessionTable,
    UserProfileTable,
    UserTable,
)


class UsersRepository(BaseRepository[User]):
    async def create(self, resource: CreateOrUpdateResource) -> User:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_id(self, id: int) -> User | None:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_username(self, username: str) -> User | None:
        stmt = (
            select("*")
            .select_from(UserTable)
            .where(eq(UserTable.c.username, username))
        )
        user = (await self.connection.execute(stmt)).first()
        if not user:
            return None
        return User(**user._asdict())

    def _get_user_id(self, session_data: str) -> int | None:
        signer = signing.TimestampSigner(
            key="<UNUSED>",
            salt="django.contrib.sessions.SessionStore",
            algorithm="sha256",
        )
        details = signer.unsign_object(
            session_data, serializer=signing.JSONSerializer
        )
        user_id = details.get("_auth_user_id")
        return None if user_id is None else int(user_id)

    async def find_by_sessionid(self, sessionid: str) -> User | None:
        stmt = (
            select(
                SessionTable.c.session_data,
            )
            .select_from(SessionTable)
            .filter(
                and_(
                    eq(SessionTable.c.session_key, sessionid),
                    gt(SessionTable.c.expire_date, datetime.utcnow()),
                )
            )
        )
        row = (await self.connection.execute(stmt)).one_or_none()
        if not row:
            return None
        session_data = row[0]
        user_id = self._get_user_id(session_data)
        if not user_id:
            return None

        stmt = (
            select("*")
            .select_from(UserTable)
            .filter(eq(UserTable.c.id, user_id))
        )
        row = (await self.connection.execute(stmt)).one_or_none()
        if not row:
            return None
        return User(**row._asdict())

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[User]:
        # TODO: use the query for the filters
        pass

    async def get_user_profile(self, username: str) -> UserProfile | None:
        stmt = (
            select(UserProfileTable.columns)
            .select_from(UserProfileTable)
            .join(UserTable, eq(UserProfileTable.c.user_id, UserTable.c.id))
            .where(eq(UserTable.c.username, username))
            .limit(1)
        )
        row = (await self.connection.execute(stmt)).one_or_none()
        print(row)
        if not row:
            return None
        return UserProfile(**row._asdict())

    async def update(self, id: int, resource: CreateOrUpdateResource) -> User:
        raise NotImplementedError("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")
