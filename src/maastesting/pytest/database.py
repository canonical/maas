from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from postgresfixture import ClusterFixture
import pytest

import maasserver.testing
from maasserver.testing.resources import create_postgres_cluster

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


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    cluster = create_postgres_cluster()
    cluster.setUp()
    early_config.stash[cluster_stash] = cluster

    early_config.stash[db_template_stash] = "maas_test"


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

    from maasserver.djangosettings import development

    settings_contents = Path(development.__file__).read_text()
    settings_name = "maasdjangotestsettings"
    tmp_python_path = Path(tempfile.mkdtemp())
    tmp_python_path.joinpath(f"{settings_name}.py").write_text(
        settings_contents.replace(
            '"NAME": "maas"', f'"NAME": "{template_name}"'
        )
    )

    old_name = development.DATABASES["default"]["NAME"]
    development.DATABASES["default"]["NAME"] = template_name

    subprocess.run(
        [
            "bin/maas-region",
            "dbupgrade",
            "--pythonpath",
            str(tmp_python_path),
            "--settings",
            settings_name,
        ]
    )
    shutil.rmtree(tmp_python_path)

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
    template = pytestconfig.stash[db_template_stash]
    dbname = f"{template}_{worker_id}"
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
    yield dbname
