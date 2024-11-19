from django.core import signing
from sqlalchemy import select

from maasapiserver.v2.models.entities.user import User
from maasservicelayer.db.tables import SessionTable, UserTable
from maasservicelayer.services._base import Service
from maasservicelayer.utils.date import utcnow


class UserService(Service):
    async def get_by_session_id(self, session_id: str) -> User | None:
        stmt = (
            select(
                SessionTable.c.session_data,
            )
            .select_from(SessionTable)
            .filter(
                SessionTable.c.session_key == session_id,
                SessionTable.c.expire_date > utcnow(),
            )
        )
        row = (await self.context.get_connection().execute(stmt)).one_or_none()
        if not row:
            return None
        session_data = row[0]
        user_id = self._get_user_id(session_data)
        if not user_id:
            return None

        stmt = (
            select(
                UserTable.c.id,
                UserTable.c.username,
                UserTable.c.email,
            )
            .select_from(UserTable)
            .filter(UserTable.c.id == user_id)
        )
        row = (await self.context.get_connection().execute(stmt)).one_or_none()
        if not row:
            return None
        return User(**row._asdict())

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
