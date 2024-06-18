#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.locks.db import DatabaseLockBase, StartupLock


class DatabaseLockBaseImpl(DatabaseLockBase):
    def __init__(self, connection: AsyncConnection):
        super().__init__(connection, 20120116, 1)


@pytest.mark.asyncio
@pytest.mark.allow_transactions
class TestDatabaseLockBase:
    async def test_commit(self, db_connection: AsyncConnection) -> None:
        # Take the lock
        async with DatabaseLockBaseImpl(db_connection):
            assert await DatabaseLockBaseImpl(db_connection).is_locked()
        assert not await DatabaseLockBaseImpl(db_connection).is_locked()


class TestStartupLock:
    async def test_commit(self, db_connection: AsyncConnection) -> None:
        connection_mock = Mock(AsyncConnection)
        lock = StartupLock(connection_mock)
        assert lock.objid == 1
        assert lock.classid == 20120116
