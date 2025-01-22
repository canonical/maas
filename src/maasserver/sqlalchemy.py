"""Make SQLALchemy available from within the Django app.

See the docstring for get_sqlalchemy_django_connection() for more info.
"""

import asyncio
from typing import Any, Coroutine, TypeVar

from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.pool import PoolProxiedConnection
from sqlalchemy.pool.base import Pool

T = TypeVar("T")


def exec_async(coro: Coroutine[Any, Any, T]) -> T:
    """Executes the coroutine `coro` in a synchronous way.

    Use only for the ServiceCollectionV3, example:

        from maasservicelayer.services import ServiceCollectionV3

        services = exec_async(ServiceCollectionV3.produce(context, cache))
        machine = exec_async(services.machines.get_by_id(1))
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # this should never happen as we are using it inside database threads
        # that do not have an async event loop.
        raise


def get_sqlalchemy_django_connection() -> Connection:
    """Get a SQLAlchemy connection sharing the Django connection.

    This returns the same kind of connection you would get if you called
    Engine.connect().

    The underlying dbapi connection is the same as the one that Django uses.

    With this you can make mix SQLAlchemy core with Django. The transaction is
    shared across both SQLAlchemy and Django.

    Django is in charge of the transaction and connection handling. When using
    SQLAlchemy core together with Django, SQLAlchemy should be used only to
    construct and make SQL queries. Starting and committing transactions should
    be done using the Django API.

    For example:

        from django.db import transaction

        conn = get_sqlalchemy_django_connection()
        with transaction.atomic():
            conn.execute(...)
    """
    from django.conf import settings
    from django.db import connection as django_connection

    django_db = settings.DATABASES[django_connection.alias]
    assert (
        django_db["ENGINE"] == "django.db.backends.postgresql"
    ), f"{django_db['ENGINE']} is not supported"

    pool = SharedDjangoPool()
    engine = Engine(
        pool=pool,
        dialect=PGDialect_psycopg2(dbapi=PGDialect_psycopg2.import_dbapi()),
        url=URL.create("postgresql+psycopg2"),
    )
    conn = SharedConnection(
        engine=engine,
        connection=SharedDBAPIConnection(django_connection.connection),
        _allow_autobegin=False,
    )
    return conn


class SharedConnection(Connection):
    """A connection that shares the dbapi connection with another framework.

    The other framework, like Django, is expected to handle the transactions,
    as well as the state of the connection.
    """

    def invalidate(self, exception=None):
        raise NotImplementedError("Underlying connection is handled by Django")

    def begin(self):
        raise NotImplementedError("Transactions are handled by Django")

    def begin_nested(self):
        raise NotImplementedError("Transactions are handled by Django")

    def begin_twophase(self, xid=None):
        raise NotImplementedError("Transactions are handled by Django")

    def commit(self):
        raise NotImplementedError("Transactions are handled by Django")

    def rollback(self):
        raise NotImplementedError("Transactions are handled by Django")


class SharedDBAPIConnection(PoolProxiedConnection):
    def __init__(self, dbapi_connection):
        self.dbapi_connection = dbapi_connection

    @property
    def driver_connection(self):
        return self.dbapi_connection

    def cursor(self):
        return self.dbapi_connection.cursor()


class SharedDjangoPool(Pool):
    """A custom pool that ensures that no connection attempts are being made."""

    def __init__(self):
        pass

    def connect(self) -> PoolProxiedConnection:
        raise NotImplementedError("Underlying connection is handled by Django")
