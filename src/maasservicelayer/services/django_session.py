# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

from django.core import signing

from maascommon.utils.strings import get_random_string
from maasservicelayer.builders.django_session import DjangoSessionBuilder
from maasservicelayer.db.repositories.django_session import (
    DjangoSessionRepository,
)
from maasservicelayer.models.configurations import SessionLengthConfig
from maasservicelayer.models.django_session import DjangoSession
from maasservicelayer.services.base import Context, Service
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.utils.date import utcnow


class DjangoSessionService(Service):
    def __init__(
        self,
        repository: DjangoSessionRepository,
        context: Context,
        config_service: ConfigurationsService,
    ):
        super().__init__(context)
        self.repository = repository
        self.config_service = config_service

    async def create_session(self, user_id: int) -> DjangoSession:
        """Function for manually creating a session, when login is done from API V3."""

        signer = signing.TimestampSigner(
            key="<UNUSED>",
            salt="django.contrib.sessions.SessionStore",
            algorithm="sha256",
        )
        session_data = signer.sign_object(  # type: ignore
            {
                "_auth_user_id": str(user_id),
                "_auth_user_backend": "django.contrib.auth.backends.ModelBackend",
            },
            serializer=signing.JSONSerializer,
        )

        session_length = await self.config_service.get(
            SessionLengthConfig.name
        )

        builder = DjangoSessionBuilder(
            session_key=get_random_string(32),
            session_data=session_data,
            expire_date=utcnow() + timedelta(seconds=session_length),
        )
        return await self.repository.create(builder)

    async def get_session(self, session_key: str) -> DjangoSession | None:
        return await self.repository.get_by_session_key(session_key)

    async def extend_session(self, session_key: str) -> DjangoSession:
        now = utcnow()
        session_length = await self.config_service.get(
            SessionLengthConfig.name
        )
        builder = DjangoSessionBuilder(
            expire_date=now + timedelta(seconds=session_length)
        )
        return await self.repository.update_by_session_key(
            session_key, builder
        )

    async def delete_session(self, session_key: str) -> None:
        await self.repository.delete_by_session_key(session_key)
