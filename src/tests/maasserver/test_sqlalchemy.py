from django.db import connection as django_connection
import pytest
from sqlalchemy import select
from sqlalchemy.sql.expression import func

from maasserver.sqlalchemy import (
    get_sqlalchemy_django_connection,
    ServiceLayerAdapter,
)
from maasserver.testing.factory import factory


def test_same_transaction(maasdb):
    conn = get_sqlalchemy_django_connection()
    stmt = select(func.txid_current())
    sqlalchemy_txid = conn.execute(stmt).scalar()
    with django_connection.cursor() as cursor:
        cursor.execute("SELECT txid_current()")
        rows = cursor.fetchall()
        django_txid = rows[0][0]
    assert sqlalchemy_txid == django_txid


def test_no_transaction_handling(maasdb):
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


def test_no_connection_handling(maasdb):
    conn = get_sqlalchemy_django_connection()
    with pytest.raises(NotImplementedError):
        conn.close()
    with pytest.raises(NotImplementedError):
        conn.invalidate()


def test_no_pool_connect(maasdb):
    conn = get_sqlalchemy_django_connection()
    with pytest.raises(NotImplementedError):
        conn.engine.pool.connect()


def test_v3_services_creation(maasdb):
    machine = factory.make_Machine()
    with ServiceLayerAdapter.build() as servicelayer:
        fetched_machine = servicelayer.services.machines.get_by_id(machine.id)
    assert fetched_machine is not None
    assert fetched_machine.id == machine.id
