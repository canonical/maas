#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class DatabaseLockNotHeld(Exception):
    """A particular lock was not held."""


class DatabaseLockBase(ABC):  # noqa: B024
    def __init__(self, connection: AsyncConnection, classid: int, objid: int):
        self.connection = connection
        self.classid = classid
        self.objid = objid

    async def __aenter__(self):
        stmt = text(f"SELECT pg_advisory_lock({self.classid}, {self.objid})")
        result = (await self.connection.execute(stmt)).one_or_none()
        if not result or result == (False,):
            raise DatabaseLockNotHeld()

    async def __aexit__(self, *exc_info):
        stmt = text(f"SELECT pg_advisory_unlock({self.classid}, {self.objid})")
        result = (await self.connection.execute(stmt)).one_or_none()
        if not result or result == (False,):
            raise DatabaseLockNotHeld()

    async def is_locked(self) -> bool:
        """
        Use the same logic of src/maasserver/utils/dblocks.py
        """
        stmt = text(
            "SELECT 1 FROM pg_locks, pg_database"
            " WHERE pg_locks.locktype = 'advisory'"
            f"   AND pg_locks.classid = {self.classid}"
            f"   AND pg_locks.objid = {self.objid}"
            # objsubid is 2 when using the 2-argument version of the
            # pg_advisory_* locking functions.
            "   AND pg_locks.objsubid = 2"
            "   AND pg_locks.granted"
            # Advisory locks are local to each database so we join to
            # pg_databases to discover the OID of the currrent database.
            "   AND pg_locks.database = pg_database.oid"
            "   AND pg_database.datname = current_database()"
        )
        lock = (await self.connection.execute(stmt)).one_or_none()
        if lock:
            return True
        return False


class StartupLock(DatabaseLockBase):
    """
    See the startup lock at src/maasserver/locks.py:23 for the original reference.
    """

    def __init__(self, connection: AsyncConnection):
        super().__init__(connection, 20120116, 1)
