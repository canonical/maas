#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from operator import eq

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.db.tables import RootKeyTable
from maasapiserver.common.utils.date import utcnow
from maasapiserver.v3.db.external_auth import ExternalAuthRepository
from tests.fixtures.factories.external_auth import create_rootkey
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestExternalAuthRepository:
    async def test_create(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        test_start = utcnow()
        external_auth_repository = ExternalAuthRepository(db_connection)
        root_key = await external_auth_repository.create()
        assert root_key.created >= test_start
        assert root_key.updated >= test_start
        assert root_key.id is not None
        assert root_key.expiration == root_key.created + timedelta(days=2)

    async def test_find_by_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        created_rootkey = await create_rootkey(fixture)
        external_auth_repository = ExternalAuthRepository(db_connection)
        rootkey = await external_auth_repository.find_by_id(created_rootkey.id)
        assert rootkey == created_rootkey

    async def test_find_by_id_not_found(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        external_auth_repository = ExternalAuthRepository(db_connection)
        rootkey = await external_auth_repository.find_by_id(-1)
        assert rootkey is None

    async def test_find_expired_keys(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow()
        expired_rootkey1 = await create_rootkey(
            fixture, expiration=now - timedelta(seconds=1)
        )
        expired_rootkey2 = await create_rootkey(
            fixture, expiration=now - timedelta(seconds=1)
        )
        valid_rootkey = await create_rootkey(fixture)

        external_auth_repository = ExternalAuthRepository(db_connection)
        rootkeys = await external_auth_repository.find_expired_keys()
        assert len(rootkeys) == 2
        assert expired_rootkey1 in rootkeys
        assert expired_rootkey2 in rootkeys
        assert valid_rootkey not in rootkeys

    async def test_find_best_key(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow()
        await create_rootkey(
            fixture,
            created=now - timedelta(minutes=60),
            expiration=now + timedelta(days=2),
        )
        best_key = await create_rootkey(
            fixture,
            created=now - timedelta(minutes=1),
            expiration=now + timedelta(days=2),
        )

        external_auth_repository = ExternalAuthRepository(db_connection)
        rootkey = await external_auth_repository.find_best_key()
        assert rootkey == best_key

    async def test_find_best_key_outside_created_interval(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow() - timedelta(seconds=1)  # simulate 1 sec delay
        created = now - timedelta(days=1)
        expiration = now + timedelta(days=1)
        await create_rootkey(fixture, created=created, expiration=expiration)

        external_auth_repository = ExternalAuthRepository(db_connection)
        rootkey = await external_auth_repository.find_best_key()
        assert rootkey is None

    async def test_find_best_key_expired(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow()
        created = now - timedelta(minutes=60)
        expiration = now - timedelta(seconds=1)
        await create_rootkey(fixture, created=created, expiration=expiration)

        external_auth_repository = ExternalAuthRepository(db_connection)
        rootkey = await external_auth_repository.find_best_key()
        assert rootkey is None

    async def test_find_best_key_outside_expired_interval(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow()
        created = now - timedelta(minutes=60)
        expiration = now + timedelta(hours=23)
        await create_rootkey(fixture, created=created, expiration=expiration)

        external_auth_repository = ExternalAuthRepository(db_connection)
        rootkey = await external_auth_repository.find_best_key()
        assert rootkey is None

    async def test_delete(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        created_rootkey = await create_rootkey(fixture)

        external_auth_repository = ExternalAuthRepository(db_connection)
        await external_auth_repository.delete(created_rootkey.id)

        rootkey = await fixture.get(
            RootKeyTable.name, eq(RootKeyTable.c.id, created_rootkey.id)
        )
        assert rootkey == []
