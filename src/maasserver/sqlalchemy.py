"""Make SQLALchemy available from within the Django app.

See the docstring for get_sqlalchemy_django_connection() for more info.
"""

import asyncio
from asyncio import AbstractEventLoop
from contextlib import contextmanager
from typing import Any, Callable, Coroutine, Iterator, Self, TypeVar

from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.pool import PoolProxiedConnection
from sqlalchemy.pool.base import Pool

from maasservicelayer.context import Context
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from maasservicelayer.services.base import Service

T = TypeVar("T")


class SyncServiceCollectionV3Adapter:
    """Wraps a ServiceCollectionV3 to automatically execute async calls synchronously."""

    def __init__(
        self,
        event_loop: AbstractEventLoop,
        service_collection: ServiceCollectionV3,
    ):
        self._event_loop = event_loop
        self._service_collection = service_collection

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._service_collection, name)

        if isinstance(attr, Service):
            return self._wrap_service(attr)

        return attr

    def _wrap_service(self, service: Service):
        class SyncServiceWrapper:
            def __init__(
                self, event_loop: AbstractEventLoop, service: Service
            ):
                self._event_loop = event_loop
                self._service = service

            def __getattr__(self, method_name: str) -> Callable:
                method = getattr(self._service, method_name)

                if asyncio.iscoroutinefunction(method):

                    def sync_wrapper(*args, **kwargs):
                        if self._event_loop.is_running():
                            raise RuntimeError(
                                "Cannot call async function from a running event loop"
                            )
                        return self._event_loop.run_until_complete(
                            method(*args, **kwargs)
                        )

                    return sync_wrapper

                return method

        return SyncServiceWrapper(self._event_loop, service)


class ServiceLayerAdapter:
    def __init__(self):
        self.event_loop = asyncio.new_event_loop()
        self.cache_for_services = CacheForServices()
        # Set ServiceCollectionV3 just to help developers to use the service layer from the django application even if it's
        # technically not the right type. However, it's fine because this adapter is supposed to be used only in the django
        # application and we will never run this process with mypy.
        self.services: ServiceCollectionV3 = SyncServiceCollectionV3Adapter(
            event_loop=self.event_loop,
            service_collection=self.exec_async(
                ServiceCollectionV3.produce(
                    Context(connection=get_sqlalchemy_django_connection()),
                    self.cache_for_services,
                )
            ),
        )

    @classmethod
    @contextmanager
    def build(cls) -> Iterator[Self]:
        instance = cls()
        try:
            yield instance
        finally:
            instance.close()

    def exec_async(self, coro: Coroutine[Any, Any, T]) -> T:
        return self.event_loop.run_until_complete(coro)

    def close(self):
        self.exec_async(self.cache_for_services.close())
        self.event_loop.close()


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
    assert django_db["ENGINE"] == "django.db.backends.postgresql", (
        f"{django_db['ENGINE']} is not supported"
    )

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
