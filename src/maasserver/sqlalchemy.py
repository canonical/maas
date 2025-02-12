# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Make SQLALchemy available from within the Django app.

See the docstring for get_sqlalchemy_django_connection() for more info.
"""

import asyncio
from asyncio import AbstractEventLoop
import threading
from typing import Any, Callable, Coroutine, TypeVar

from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.pool import PoolProxiedConnection
from sqlalchemy.pool.base import Pool

from maasservicelayer.context import Context
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from maasservicelayer.services.base import Service


class ServiceLayerNotInitialized(Exception):
    """Service Layer must be initialized first"""


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
        """
        Intercept attribute access.
        If the attribute is a service, wrap it in a synchronous adapter.
        """
        attr = getattr(self._service_collection, name)

        if isinstance(attr, Service):
            return self._wrap_service(attr)

        return attr

    def _wrap_service(self, service: Service):
        """Wraps an async service so its methods can be called synchronously."""

        class SyncServiceWrapper:
            def __init__(
                self, event_loop: AbstractEventLoop, service: Service
            ):
                self._event_loop = event_loop
                self._service = service

            def __getattr__(self, method_name: str) -> Callable:
                """
                Intercept method access. If the method is async, wrap it to run synchronously.
                """
                method = getattr(self._service, method_name)

                if asyncio.iscoroutinefunction(method):

                    def sync_wrapper(*args, **kwargs):
                        """
                        Executes async functions synchronously using the event loop.
                        Prevents execution if the event loop is already running.
                        """
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


T = TypeVar("T")


class ServiceLayerAdapter(threading.local):
    def __init__(self):
        super().__init__()
        self.initialized = False
        self.event_loop = None
        self.cache_for_services = None
        self.context = None
        self._services = None

    def init(self):
        """Initializes the service layer adapter with necessary components."""
        self.initialized = True
        self.event_loop = asyncio.new_event_loop()
        self.cache_for_services = CacheForServices()
        self.context = Context(connection=get_sqlalchemy_django_connection())
        self._services = SyncServiceCollectionV3Adapter(
            event_loop=self.event_loop,
            service_collection=self.exec_async(
                ServiceCollectionV3.produce(
                    self.context,
                    self.cache_for_services,
                )
            ),
        )

    # Set ServiceCollectionV3 just to help developers to use the service layer from the django application even if it's
    # technically not the right type. However, it's fine because this adapter is supposed to be used only in the django
    # application and we will never run this process with mypy.
    @property
    def services(self) -> ServiceCollectionV3:
        """Provides access to the service collection, ensuring initialization."""
        self._guard_initialization()
        return self._services

    def ensure_connection(self):
        """Ensures the database connection is active and updates it if necessary."""
        self._guard_initialization()
        # If the connection has been closed and our orm.py has reopened it, we have to pick the new one.
        if self.context.get_connection().connection.dbapi_connection.closed:
            self.context.set_connection(get_sqlalchemy_django_connection())

    def exec_async(self, coro: Coroutine[Any, Any, T]) -> T:
        """Executes an asynchronous coroutine synchronously within the event loop."""
        self._guard_initialization()
        return self.event_loop.run_until_complete(coro)

    def close(self):
        """Closes the service layer adapter, releasing resources."""
        if self.initialized:
            self.exec_async(self.cache_for_services.close())
            self.event_loop.close()
        self.initialized = False

    def _guard_initialization(self):
        """Checks if the adapter has been initialized before allowing access to resources."""
        if not self.initialized:
            raise ServiceLayerNotInitialized(
                "Service layer not initialized in this thread. This is likely to be a programming error and should never happen."
            )

    def __del__(self):
        self.close()


service_layer = ServiceLayerAdapter()


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
