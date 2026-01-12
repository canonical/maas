# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from django.core import signing
import pytest

from maasservicelayer.builders.django_session import DjangoSessionBuilder
from maasservicelayer.db.repositories.django_session import (
    DjangoSessionRepository,
)
from maasservicelayer.models.django_session import DjangoSession
from maasservicelayer.services.base import Context
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.django_session import DjangoSessionService
from maasservicelayer.utils.date import utcnow

TEST_SESSION = DjangoSession(
    session_key="testsessionkey",
    session_data="testsessiondata",
    expire_date=datetime(2025, 12, 31, 23, 59, 59),
)


class TestDjangoSessionService:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.configurations_service = Mock(ConfigurationsService)
        self.repository = Mock(DjangoSessionRepository)

        self.service = DjangoSessionService(
            context=Context(),
            repository=self.repository,
            config_service=self.configurations_service,
        )

    @patch("maasservicelayer.services.django_session.get_random_string")
    @patch("maasservicelayer.services.django_session.utcnow")
    async def test_create_session(
        self,
        utcnow_mock: MagicMock,
        get_random_string_mock: MagicMock,
    ) -> None:
        now = utcnow()
        utcnow_mock.return_value = now
        self.configurations_service.get = AsyncMock(return_value=3600)
        user_id = 1
        get_random_string_mock.return_value = TEST_SESSION.session_key
        self.repository.create = AsyncMock(return_value=TEST_SESSION)
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

        builder = DjangoSessionBuilder(
            session_key=TEST_SESSION.session_key,
            session_data=session_data,
            expire_date=now + timedelta(seconds=3600),
        )

        result = await self.service.create_session(user_id)

        self.repository.create.assert_awaited_once_with(builder)
        assert result == TEST_SESSION
        assert isinstance(result, DjangoSession)

    async def test_get_session(
        self,
    ) -> None:
        self.repository.get_by_session_key = AsyncMock(
            return_value=TEST_SESSION
        )

        result = await self.service.get_session(TEST_SESSION.session_key)

        self.repository.get_by_session_key.assert_awaited_once_with(
            TEST_SESSION.session_key
        )
        assert result == TEST_SESSION
        assert isinstance(result, DjangoSession)

    @patch("maasservicelayer.services.django_session.utcnow")
    async def test_extend_session(
        self,
        utcnow_mock: MagicMock,
    ) -> None:
        now = utcnow()
        utcnow_mock.return_value = now
        self.configurations_service.get = AsyncMock(return_value=3600)
        builder = DjangoSessionBuilder(
            expire_date=now + timedelta(seconds=3600)
        )
        self.repository.update_by_session_key = AsyncMock(
            return_value=TEST_SESSION
        )

        await self.service.extend_session(TEST_SESSION.session_key)

        self.repository.update_by_session_key.assert_awaited_once_with(
            TEST_SESSION.session_key, builder
        )

    async def test_delete_session(
        self,
    ) -> None:
        self.repository.delete_by_session_key = AsyncMock()

        await self.service.delete_session(TEST_SESSION.session_key)

        self.repository.delete_by_session_key.assert_awaited_once_with(
            TEST_SESSION.session_key
        )
