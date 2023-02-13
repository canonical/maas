from contextlib import contextmanager
import os
from pathlib import Path

from django.db import transaction
from postgresfixture import ClusterFixture
import pytest

from maasserver.djangosettings import development
import maasserver.testing
from maasserver.testing.resources import (
    close_all_connections,
    create_postgres_cluster,
)
from maasserver.utils.orm import enable_all_database_connections

cluster_stash = pytest.StashKey[ClusterFixture]()
db_template_stash = pytest.StashKey[str]()


def pytest_addoption(parser):
    default_initial_db = (
        Path(maasserver.testing.__file__).parent / "initial.maas_test.sql"
    )
    maas_parser = parser.getgroup("maas", description="MAAS")
    maas_parser.addoption(
        "--maas-recreate-initial-db",
        help="Recreate the DB template that's used to speed up tests",
        action="store_true",
    )
    maas_parser.addoption(
        "--maas-initial-db",
        help="The initial DB dump that's used to create the DB template.",
        default=str(default_initial_db),
    )


def load_initial_db_file(cluster, template_name, path):
    if path.suffix == ".sql":
        with connect(cluster) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE "{template_name}"')
        cluster.execute(
            "psql",
            "--quiet",
            "--single-transaction",
            "--set=ON_ERROR_STOP=1",
            "--dbname",
            template_name,
            "--output",
            os.devnull,
            "--file",
            str(path),
        )
    else:
        # Assume it's a DB dump of the "maas" database.
        cluster.execute(
            "pg_restore",
            "-O",
            "-x",
            "--disable-triggers",
            "--create",
            "--clean",
            "--if-exists",
            "-d",
            "postgres",
            str(path),
        )
        with connect(cluster) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f'ALTER DATABASE "maas" RENAME TO "{template_name}"'
                )


@contextmanager
def connect(cluster):
    conn = cluster.connect()
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.hookimpl(tryfirst=False)
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "allow_transactions: Allow a test to use transaction.commit()",
    )
    config.addinivalue_line(
        "markers",
        "recreate_db: re-create database before each test run",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    cluster = create_postgres_cluster()
    cluster.setUp()
    early_config.stash[cluster_stash] = cluster
    os.environ[
        "DJANGO_SETTINGS_MODULE"
    ] = "maasserver.djangosettings.development"
    import django

    from maasserver.djangosettings import development

    database = development.DATABASES["default"]
    template = f"{database['NAME']}_test"
    early_config.stash[db_template_stash] = template
    database["NAME"] = "no_such_db"
    django.setup()


@pytest.hookimpl
def pytest_unconfigure(config):
    cluster = config.stash[cluster_stash]
    cluster.cleanUp()


def _set_up_template_db(
    cluster, template_name, template_path, force_recreate=False
):
    if force_recreate:
        with connect(cluster) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f'DROP DATABASE IF EXISTS "{template_name}"')

    if template_name not in cluster.databases:
        load_initial_db_file(cluster, template_name, template_path)

    from django.core.management import call_command

    from maasserver import dbviews, triggers
    from maasserver.djangosettings import development

    old_name = development.DATABASES["default"]["NAME"]
    development.DATABASES["default"]["NAME"] = template_name

    import django

    django.setup()
    enable_all_database_connections()
    dbviews.drop_all_views()
    call_command("migrate", interactive=False)

    triggers.register_all_triggers()
    dbviews.register_all_views()

    close_all_connections()
    development.DATABASES["default"]["NAME"] = old_name


@pytest.fixture(scope="session")
def templatemaasdb(pytestconfig):
    cluster = pytestconfig.stash[cluster_stash]
    force_recreate = pytestconfig.option.maas_recreate_initial_db
    template_path = Path(pytestconfig.option.maas_initial_db)
    with cluster.lock.exclusive:
        template_name = pytestconfig.stash[db_template_stash]
        _set_up_template_db(
            cluster, template_name, template_path, force_recreate
        )


@pytest.fixture
def ensuremaasdb(request, templatemaasdb, pytestconfig, worker_id):
    from maasserver.djangosettings import development

    template = pytestconfig.stash[db_template_stash]
    dbname = f"{template}_{worker_id}"
    database = development.DATABASES["default"]
    database["NAME"] = dbname
    cluster = pytestconfig.stash[cluster_stash]
    template = pytestconfig.stash[db_template_stash]
    with (
        cluster.lock.exclusive,
        connect(cluster) as conn,
        conn.cursor() as cursor,
    ):
        if request.node.get_closest_marker("recreate_db"):
            cursor.execute(f"DROP DATABASE IF EXISTS {dbname}")
        if dbname not in cluster.databases:
            cursor.execute(
                f'CREATE DATABASE "{dbname}" WITH TEMPLATE "{template}"'
            )
    yield
    database["NAME"] = "no_such_db"


@pytest.fixture
def maasdb(ensuremaasdb, request, pytestconfig):
    enable_all_database_connections()
    # Start a transaction.
    transaction.set_autocommit(False)
    allow_transactions = (
        request.node.get_closest_marker("allow_transactions") is not None
    )
    if allow_transactions:
        yield
        close_all_connections()
        # Since transactions are allowed, we assume a commit has been
        # made, so we can't simply do rollback to clean up the DB.
        dbname = development.DATABASES["default"]["NAME"]
        cluster = pytestconfig.stash[cluster_stash]
        cluster.dropdb(dbname)
    else:
        # Wrap the test in an atomic() block in order to prevent commits.
        with transaction.atomic():
            yield
        # Since we don't allow commits, we can safely rollback and don't
        # have to recreate the DB.
        transaction.rollback()
        close_all_connections()


@pytest.fixture
def factory(maasdb):
    # Local imports from maasserver so that pytest --help works
    from maasserver.testing.factory import factory as maasserver_factory

    return maasserver_factory


@pytest.fixture
def admin(factory):
    return factory.make_admin()


@pytest.fixture
def maas_user(factory):
    return factory.make_User()


@pytest.fixture
def api_client(maas_user):
    # Local imports from maasserver so that pytest --help works
    from maasserver.models.user import get_auth_tokens
    from maasserver.testing.testclient import MAASSensibleOAuthClient

    return MAASSensibleOAuthClient(
        user=maas_user, token=get_auth_tokens(maas_user)[0]
    )


@pytest.fixture
def admin_api_client(admin):
    # Local imports from maasserver so that pytest --help works
    from maasserver.models.user import get_auth_tokens
    from maasserver.testing.testclient import MAASSensibleOAuthClient

    return MAASSensibleOAuthClient(user=admin, token=get_auth_tokens(admin)[0])
