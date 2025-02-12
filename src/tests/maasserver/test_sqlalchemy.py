# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from unittest.mock import Mock

from django.db import connection as django_connection
from django.db import transaction
import pytest
from sqlalchemy import select
from sqlalchemy.sql.expression import func

from maasserver.sqlalchemy import (
    get_sqlalchemy_django_connection,
    service_layer,
    ServiceLayerAdapter,
    ServiceLayerNotInitialized,
    SyncServiceCollectionV3Adapter,
)
from maasserver.testing.factory import factory
from maasserver.testing.resources import close_all_connections
from maasserver.utils.orm import enable_all_database_connections
from maasservicelayer.context import Context
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.base import Service


@pytest.mark.usefixtures("maasdb")
class TestGetSqlalchemyConnection:
    def test_same_transaction(self):
        conn = get_sqlalchemy_django_connection()
        stmt = select(func.txid_current())
        sqlalchemy_txid = conn.execute(stmt).scalar()
        with django_connection.cursor() as cursor:
            cursor.execute("SELECT txid_current()")
            rows = cursor.fetchall()
            django_txid = rows[0][0]
        assert sqlalchemy_txid == django_txid

    def test_no_transaction_handling(self):
        conn = get_sqlalchemy_django_connection()
        with pytest.raises(NotImplementedError):
            conn.begin()
        with pytest.raises(NotImplementedError):
            conn.commit()
        with pytest.raises(NotImplementedError):
            conn.rollback()
        with pytest.raises(NotImplementedError):
            conn.begin_twophase()
        with pytest.raises(NotImplementedError):
            conn.begin_nested()

    def test_no_connection_handling(self):
        conn = get_sqlalchemy_django_connection()
        with pytest.raises(NotImplementedError):
            conn.close()
        with pytest.raises(NotImplementedError):
            conn.invalidate()

    def test_no_pool_connect(self):
        conn = get_sqlalchemy_django_connection()
        with pytest.raises(NotImplementedError):
            conn.engine.pool.connect()


class StubService(Service):
    def __init__(self):
        super().__init__(Mock(Context))
        self.my_property = "my_property"

    async def async_method(self):
        return "async"

    def sync_method(self):
        return "sync"


class TestSyncServiceCollectionV3Adapter:
    def test_service_access_returns_wrapped_service(self):
        event_loop = asyncio.new_event_loop()
        mock_service_collection = Mock(ServiceCollectionV3)
        mock_service_collection.stub_service = StubService()

        adapter = SyncServiceCollectionV3Adapter(
            event_loop, mock_service_collection
        )
        wrapped_stub_service = adapter.stub_service

        assert hasattr(wrapped_stub_service, "async_method")
        assert not asyncio.iscoroutine(wrapped_stub_service.async_method)
        assert wrapped_stub_service.async_method() == "async"

        assert hasattr(wrapped_stub_service, "sync_method")
        assert not asyncio.iscoroutine(wrapped_stub_service.sync_method)
        assert wrapped_stub_service.sync_method() == "sync"

        assert hasattr(wrapped_stub_service, "my_property")
        assert wrapped_stub_service.my_property == "my_property"

        event_loop.close()

    def test_adapter_does_not_wrap_other_classes(self):
        mock_event_loop = Mock()
        mock_service_collection = Mock(ServiceCollectionV3)
        mock_service_collection.property = "property"

        adapter = SyncServiceCollectionV3Adapter(
            mock_event_loop, mock_service_collection
        )
        assert adapter.property == "property"


class TestServiceLayerAdapter:
    def test_ensure_initialized(self):
        adapter = ServiceLayerAdapter()
        with pytest.raises(ServiceLayerNotInitialized):
            adapter.ensure_connection()

        with pytest.raises(ServiceLayerNotInitialized):

            async def coro():
                pass

            adapter.exec_async(coro())

        with pytest.raises(ServiceLayerNotInitialized):
            adapter.services  # noqa: B018

    def test_exec_async(self, maasdb):
        adapter = ServiceLayerAdapter()
        adapter.init()

        async def coro():
            return "coro"

        assert adapter.exec_async(coro()) == "coro"
        adapter.close()

    def test_services(self, maasdb):
        adapter = ServiceLayerAdapter()
        adapter.init()
        assert adapter.services.machines.list(1, 1).total == 0
        adapter.close()

    def test_close(self, maasdb):
        adapter = ServiceLayerAdapter()
        adapter.init()
        adapter.close()
        assert adapter.event_loop.is_closed()

    def test_close_doesn_not_raise_when_not_initialized(self, maasdb):
        adapter = ServiceLayerAdapter()
        adapter.close()

    def test_ensure_connection(self, ensuremaasdjangodb):
        enable_all_database_connections()
        # Start a transaction.
        transaction.set_autocommit(False)

        adapter = ServiceLayerAdapter()
        adapter.init()
        adapter.ensure_connection()

        first_connection = adapter.context.get_connection()

        # Close and reopen connections
        close_all_connections()
        enable_all_database_connections()
        transaction.set_autocommit(False)

        # The adapter should detect that the first connection was dropped and it should pick the new one.
        assert (
            adapter.context.get_connection().connection.dbapi_connection.closed
            == 1
        )
        adapter.ensure_connection()
        assert (
            adapter.context.get_connection().connection.dbapi_connection.closed
            == 0
        )
        assert first_connection is not adapter.context.get_connection()

        adapter.close()
        close_all_connections()

    def test_service_layer_from_module(self, maasdb):
        machine = factory.make_Machine()
        fetched_machine = service_layer.services.machines.get_by_id(machine.id)
        assert fetched_machine is not None
        assert fetched_machine.id == machine.id
