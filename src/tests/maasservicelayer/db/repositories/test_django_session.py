# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.django_session import DjangoSessionBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.django_session import (
    DjangoSessionRepository,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.django_session import DjangoSession
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.user import create_test_session
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestDjangoSessionRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> DjangoSessionRepository:
        return DjangoSessionRepository(
            context=Context(connection=db_connection)
        )

    @pytest.fixture
    async def instance(self, fixture: Fixture) -> DjangoSession:
        return await create_test_session(fixture, user_id=123)

    @pytest.fixture
    async def builder(self) -> DjangoSessionBuilder:
        return DjangoSessionBuilder(
            session_key="testsessionkey",
            session_data="testdata",
            expire_date=utcnow() + timedelta(seconds=3600),
        )

    async def test_create_success(
        self,
        repository: DjangoSessionRepository,
        builder: DjangoSessionBuilder,
    ) -> None:
        created_session = await repository.create(builder)
        assert created_session.session_key == "testsessionkey"
        assert created_session.session_data == "testdata"

    async def test_create_already_exists(
        self,
        repository: DjangoSessionRepository,
        instance: DjangoSession,
        builder: DjangoSessionBuilder,
    ) -> None:
        builder.session_key = instance.session_key
        with pytest.raises(AlreadyExistsException) as exc_info:
            await repository.create(builder)
        details = exc_info.value.details
        assert details is not None
        assert details[0].type == UNIQUE_CONSTRAINT_VIOLATION_TYPE
        assert (
            details[0].message
            == "A resource with such identifiers already exist."
        )

    async def test_get_by_session_key_found(
        self, repository: DjangoSessionRepository, instance: DjangoSession
    ) -> None:
        fetched_session = await repository.get_by_session_key(
            instance.session_key
        )
        assert fetched_session == instance

    async def test_get_by_session_key_not_found(
        self, repository: DjangoSessionRepository
    ) -> None:
        fetched_session = await repository.get_by_session_key(
            "nonexistentsessionkey"
        )
        assert fetched_session is None

    async def test_update_by_session_key_success(
        self,
        repository: DjangoSessionRepository,
        instance: DjangoSession,
        builder: DjangoSessionBuilder,
    ) -> None:
        builder.session_key = instance.session_key
        updated_session = await repository.update_by_session_key(
            instance.session_key, builder
        )
        assert updated_session is not None
        assert updated_session.expire_date == builder.expire_date
        assert updated_session.session_key == instance.session_key
        assert updated_session.session_data == builder.session_data

    async def test_update_by_session_key_not_found(
        self,
        repository: DjangoSessionRepository,
        builder: DjangoSessionBuilder,
    ) -> None:
        with pytest.raises(NotFoundException) as exc_info:
            await repository.update_by_session_key(
                "nonexistentsessionkey", builder
            )
        details = exc_info.value.details
        assert details is not None
        assert details[0].type == UNEXISTING_RESOURCE_VIOLATION_TYPE
        assert (
            details[0].message
            == "Resource with such identifiers does not exist."
        )

    async def test_delete_by_session_key(
        self, repository: DjangoSessionRepository, instance: DjangoSession
    ) -> None:
        await repository.delete_by_session_key(instance.session_key)
        fetched_session = await repository.get_by_session_key(
            instance.session_key
        )
        assert fetched_session is None
