# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from django.core import signing

from maascommon.utils.strings import get_random_string
from maasservicelayer.builders.django_session import DjangoSessionBuilder
from maasservicelayer.db.repositories.django_session import (
    DjangoSessionRepository,
)
from maasservicelayer.models.django_session import DjangoSession
from maasservicelayer.services.base import Context, Service


class DjangoSessionService(Service):
    def __init__(
        self,
        repository: DjangoSessionRepository,
        context: Context,
    ):
        super().__init__(context)
        self.repository = repository

    async def create_session(
        self, user_id: int, expires_at: datetime
    ) -> DjangoSession:
        """Function for manually creating a session, when login is done from API V3."""

        signer = signing.TimestampSigner(
            key="<UNUSED>",
            salt="django.contrib.sessions.SessionStore",
            algorithm="sha256",
        )
        session_data = signer.sign_object(  # type: ignore
            {
                "_auth_user_id": str(user_id),
            },
            serializer=signing.JSONSerializer,
        )
        builder = DjangoSessionBuilder(
            session_key=get_random_string(32),
            session_data=session_data,
            expire_date=expires_at,
        )
        return await self.repository.create(builder)

    async def get_session(self, session_key: str) -> DjangoSession | None:
        return await self.repository.get_by_session_key(session_key)

    async def extend_session(
        self, session_key: str, expires_at: datetime
    ) -> DjangoSession:
        builder = DjangoSessionBuilder(expire_date=expires_at)
        return await self.repository.update_by_session_key(
            session_key, builder
        )

    async def delete_session(self, session_key: str) -> None:
        await self.repository.delete_by_session_key(session_key)
