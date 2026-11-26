# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
from django.db import connection
import pytest

from maasserver.enum import SERVICE_STATUS
from maasserver.models import Service
from maasserver.sqlalchemy import get_sqlalchemy_django_connection

migration = import_module(
    "maasservicelayer.db.alembic.versions.0049_rename_agent_to_rackcontroller"
)

OLD_TABLE = "maasserver_agent"
NEW_TABLE = "maasserver_rackcontroller"


def upgrade():
    connection = get_sqlalchemy_django_connection()
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()


def execute(query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        if cursor.description is not None:
            return cursor.fetchall()
    return None


def table_exists(table):
    [(oid,)] = execute("SELECT to_regclass(%s)", [table])
    return oid is not None


def constraint_names(table):
    return {
        name
        for (name,) in execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass",
            [table],
        )
    }


def column_names(table):
    return {
        name
        for (name,) in execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s",
            [table],
        )
    }


def identity_sequence(table):
    [(sequence,)] = execute("SELECT pg_get_serial_sequence(%s, 'id')", [table])
    return sequence


def revert_to_agent_schema():
    for old_name, new_name in migration._CONSTRAINT_RENAMES:
        execute(
            f"ALTER TABLE {NEW_TABLE} RENAME CONSTRAINT {new_name} TO {old_name}"
        )
    # Generated NOT NULL constraint names on PostgreSQL 18+.
    for name in constraint_names(NEW_TABLE):
        if name.startswith(f"{NEW_TABLE}_"):
            old_name = name.replace(NEW_TABLE, OLD_TABLE, 1)
            execute(
                f'ALTER TABLE {NEW_TABLE} RENAME CONSTRAINT "{name}" '
                f'TO "{old_name}"'
            )
    execute(
        f"ALTER TABLE {NEW_TABLE} RENAME COLUMN node_id TO rackcontroller_id"
    )
    execute(f"ALTER SEQUENCE {NEW_TABLE}_id_seq RENAME TO {OLD_TABLE}_id_seq")
    execute(f"ALTER TABLE {NEW_TABLE} RENAME TO {OLD_TABLE}")


@pytest.mark.usefixtures("maasdb")
class TestRenameAgentToRackController:
    def test_restores_current_schema(self):
        constraints = constraint_names(NEW_TABLE)
        columns = column_names(NEW_TABLE)
        sequence = identity_sequence(NEW_TABLE)
        revert_to_agent_schema()
        assert not table_exists(NEW_TABLE)
        assert all(OLD_TABLE in name for name in constraint_names(OLD_TABLE))

        upgrade()

        assert not table_exists(OLD_TABLE)
        assert constraint_names(NEW_TABLE) == constraints
        assert column_names(NEW_TABLE) == columns
        assert identity_sequence(NEW_TABLE) == sequence

    def test_preserves_rows(self, factory):
        node = factory.make_RackController()
        [(rack_id,)] = execute(
            "INSERT INTO maasserver_rack (created, updated, name) "
            "VALUES (now(), now(), 'rack') RETURNING id"
        )
        revert_to_agent_schema()
        [(agent_id,)] = execute(
            f"INSERT INTO {OLD_TABLE} "
            "(created, updated, uuid, rack_id, rackcontroller_id) "
            "VALUES (now(), now(), 'uuid', %s, %s) RETURNING id",
            [rack_id, node.id],
        )
        # Pending deferred FK checks would block the ALTER TABLE statements.
        execute("SET CONSTRAINTS ALL IMMEDIATE")

        upgrade()

        assert execute(
            f"SELECT id, uuid, rack_id, node_id FROM {NEW_TABLE}"
        ) == [(agent_id, "uuid", rack_id, node.id)]
        [(next_id,)] = execute(
            f"INSERT INTO {NEW_TABLE} (created, updated, uuid, rack_id) "
            "VALUES (now(), now(), 'other-uuid', %s) RETURNING id",
            [rack_id],
        )
        assert next_id > agent_id

    def test_renames_agent_service_status(self, factory):
        rack_controller = factory.make_RackController()
        Service.objects.filter(
            node=rack_controller, name="rack-controller"
        ).update(name="agent", status=SERVICE_STATUS.RUNNING)
        revert_to_agent_schema()

        upgrade()

        service = Service.objects.get(
            node=rack_controller, name="rack-controller"
        )
        assert service.status == SERVICE_STATUS.RUNNING
        assert not Service.objects.filter(
            node=rack_controller, name="agent"
        ).exists()
