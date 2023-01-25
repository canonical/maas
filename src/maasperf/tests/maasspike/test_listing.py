"""Performance tests for the machine listing spike.

All tests that test the performance of the different implementations for the
machine listing spike should go in this file.

For each implemenation, we should have a test that lists all machines, and
a test that list 50 machines.

Each test should measure how long it takes to produce the list, and then
assert that the listing is the same as the original websocket handler.
"""

from operator import itemgetter
import time

import pytest

from maasserver.models import Machine
from maasserver.websockets.handlers.machine import MachineHandler
from maasspike import (
    baseline,
    django_light,
    plain_sql,
    sqlalchemy_core,
    sqlalchemy_orm,
)


class ExpectedMachines:
    def __init__(self, expected_list):
        self._expected_list = expected_list

    def assert_list(self, machine_list, limit=None):
        """Assert that the passed in machine list is correct.

        Compare the number of machines in each list, as well as making
        sure that the first and last machine of each list are equal.

        Comparing the full list takes too long if you have a list of
        1000 machines.
        """
        assert isinstance(machine_list, list)
        expected_list = (
            self._expected_list[:limit] if limit else self._expected_list
        )
        assert [machine["id"] for machine in machine_list] == [
            machine["id"] for machine in expected_list
        ]
        self.assert_machines(machine_list[0], expected_list[0])
        self.assert_machines(machine_list[-1], expected_list[-1])

    def assert_machines(self, machine1, machine2):
        # sort fields that don't have a strict order, for comparison
        for item in (
            "tags",
            "extra_macs",
            "fabrics",
            ("ip_addresses", itemgetter("ip")),
        ):
            if isinstance(item, tuple):
                key, sort_key = item
            else:
                key, sort_key = item, None
            machine1[key].sort(key=sort_key)
            machine2[key].sort(key=sort_key)
        assert machine1 == machine2


def get_expected_machines(admin):
    """Get the list of machines that the normal websocket handler returns."""
    machine_count = Machine.objects.all().count()
    ws_handler = MachineHandler(admin, {}, None)
    params = {
        "filter": {},
        "page_number": 1,
        "page_size": machine_count + 1,
        "sort_direction": "ascending",
        "sort_key": "hostname",
    }
    result = ws_handler.list(params)
    return ExpectedMachines(result["groups"][0]["items"])


@pytest.fixture(scope="session")
def _expected():
    """Helper fixture to store the expected machine list for the session.

    A session fixture doesn't have access to the DB, so we make use of a
    function fixture, expected_machines, to get the machine listing
    for the first test and store it here.

    The fixture shouldn't be used by any test.
    """
    return {}


@pytest.fixture
def expected_machines(admin, _expected):
    if "machines" not in _expected:
        _expected["machines"] = get_expected_machines(admin)
    return _expected["machines"]


@pytest.fixture
def machine_listing_materialized_view(ensuremaasdb, psycopg_conn):

    from maasspike.plain_sql import get_query

    query, params = get_query(limit=None)  # always include all machines

    view_name = "maasspike_machine_listing"
    with psycopg_conn.cursor() as cur:
        cur.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}")
        cur.execute(f"CREATE MATERIALIZED VIEW {view_name} AS {query}", params)
    yield view_name
    with psycopg_conn.cursor() as cur:
        cur.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}")


@pytest.fixture
def sqlalchemy_engine(ensuremaasdb):
    import sqlalchemy

    from maasserver.djangosettings import development

    params = development.DATABASES["default"]
    connect_url = f"postgresql:///{params['NAME']}?host={params['HOST']}"
    engine = sqlalchemy.create_engine(connect_url)
    yield engine
    engine.dispose()


@pytest.fixture
def sqlalchemy_conn(sqlalchemy_engine):
    with sqlalchemy_engine.connect() as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def sqlalchemy_session(sqlalchemy_engine):
    from sqlalchemy.orm import Session

    with Session(sqlalchemy_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def psycopg_conn():
    from django.db import connection
    from psycopg2 import connect
    from psycopg2.extensions import connection as pg_connection
    from psycopg2.extras import NamedTupleCursor

    # track queries for psycopg in the django connection since the psycopg one
    # isn't modifiable
    query_track = {"count": 0, "time": 0.0}
    connection._psycopg_track = query_track

    class QueryLoggingCursor(NamedTupleCursor):
        """Track query count/time

        This extends the NuamedTupleCursor since it's the one used by tests.
        """

        def execute(self, *args, **kwargs):
            query_track["count"] += 1
            start = time.perf_counter()
            result = super().execute(*args, **kwargs)
            query_track["time"] += time.perf_counter() - start
            return result

    class QueryLoggingConnection(pg_connection):
        def cursor(self, *args, **kwargs):
            kwargs["cursor_factory"] = QueryLoggingCursor
            return super().cursor(*args, **kwargs)

    conn = connect(
        dsn=connection.connection.dsn,
        connection_factory=QueryLoggingConnection,
    )
    yield conn
    conn.close()
    delattr(connection, "_psycopg_track")


def test_populate_expected_machines(expected_machines):
    """A blank test to populate the expected_machines fixture.

    This should be the first test to be run, so that other test
    don't get any advantage by having the query to the machine
    listing cached.
    """


@pytest.mark.skip(reason="Not worth using sqlalchemy ORM")
def test_sqlalchemy_prime(sqlalchemy_session):
    from sqlalchemy import select

    list(sqlalchemy_session.execute(select(sqlalchemy_orm.Machine)))
    list(sqlalchemy_session.execute(select(sqlalchemy_orm.Tag)))
    list(sqlalchemy_session.execute(select(sqlalchemy_orm.Zone)))
    list(sqlalchemy_session.execute(select(sqlalchemy_orm.ResourcePool)))
    list(sqlalchemy_session.execute(select(sqlalchemy_orm.User)))
    list(sqlalchemy_session.execute(select(sqlalchemy_orm.Domain)))


@pytest.mark.parametrize("limit", [None, 50])
class TestListing:
    """Collection of tests for spike machine listing implementations.

    A class is used to group the tests together to ensure they measure
    and assert the same thing.

    Each implementation should have a test that does the required setup
    and then call self.run_listing_test.

    Each test is run once using the full listing, and once using the first
    50 machines.
    """

    @pytest.fixture(autouse=True)
    def set_up(self, perf, admin, expected_machines):
        self._expected_machines = expected_machines
        self._admin = admin
        self._perf = perf
        yield
        self._expected_machines = None
        self._admin = None
        self._perf = None

    def run_listing_test(self, name, func, limit):
        record_name = f"maasspike_{name}"
        if limit:
            record_name += f"_{limit}"
        else:
            record_name += "_all"
        with self._perf.record(record_name):
            machines = func(self._admin, limit)
        self._expected_machines.assert_list(machines, limit)

    def test_baseline(self, limit):
        self.run_listing_test("baseline", baseline.list_machines, limit)

    def test_django_light(self, limit):
        self.run_listing_test(
            "django_light", django_light.list_machines, limit
        )

    @pytest.mark.skip(reason="Not worth using sqlalchemy ORM")
    def test_sqlalchemy_orm(self, limit, sqlalchemy_session):
        self.run_listing_test(
            "sqlalchemy_orm",
            lambda admin, limit: sqlalchemy_orm.list_machines(
                sqlalchemy_session,
                admin,
                limit,
            ),
            limit,
        )

    def test_sqlalchemy_core_one_query(self, limit, sqlalchemy_conn):
        self.run_listing_test(
            "sqlalchemy_core_one_query",
            lambda admin, limit: sqlalchemy_core.list_machines_one_query(
                sqlalchemy_conn,
                admin,
                limit,
            ),
            limit,
        )

    def test_sqlalchemy_core_multiple_queries(self, limit, sqlalchemy_conn):
        self.run_listing_test(
            "sqlalchemy_core_multiple_queries",
            lambda admin, limit: sqlalchemy_core.list_machines_multiple_queries(
                sqlalchemy_conn,
                admin,
                limit,
            ),
            limit,
        )

    def test_plain_sql_one_query(self, limit, psycopg_conn):
        self.run_listing_test(
            "plain_sql_one_query",
            lambda admin, limit: plain_sql.list_machines_one_query(
                psycopg_conn,
                admin,
                limit,
            ),
            limit,
        )

    def test_materialized_view(
        self, limit, psycopg_conn, machine_listing_materialized_view
    ):
        self.run_listing_test(
            "materialized_view",
            lambda admin, limit: plain_sql.list_machines_materialized_view(
                psycopg_conn,
                machine_listing_materialized_view,
                admin,
                limit,
            ),
            limit,
        )
