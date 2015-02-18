# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Triggers

Triggers are implemented in the database to notify the PostgresListener when
an event occurs. Each trigger should use "CREATE OR REPLACE" so its overrides
its previous trigger. All triggers will be added into the database via the
`start_up` method for regiond.

Each trigger will call a procedure to send the notification. Each procedure
should be named with the table name "maasserver_node" and the action for the
trigger "node_create" followed by "notify".

E.g. "maasserver_node_node_create_notify".
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "register_all_triggers"
    ]

from contextlib import closing
from textwrap import dedent

from django.db import connection
from maasserver.utils.async import transactional


NODE_CREATE_PROCEDURE = dedent("""\
    CREATE OR REPLACE FUNCTION node_create_notify() RETURNS trigger AS $$
    DECLARE
    BEGIN
      PERFORM pg_notify('node_create',CAST(NEW.system_id AS text));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

NODE_UPDATE_PROCEDURE = dedent("""\
    CREATE OR REPLACE FUNCTION node_update_notify() RETURNS trigger AS $$
    DECLARE
    BEGIN
      PERFORM pg_notify('node_update',CAST(NEW.system_id AS text));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

NODE_DELETE_PROCEDURE = dedent("""\
    CREATE OR REPLACE FUNCTION node_delete_notify() RETURNS trigger AS $$
    DECLARE
    BEGIN
      PERFORM pg_notify('node_delete',CAST(OLD.system_id AS text));
      RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """)


def register_trigger(table, procedure, event, when="after"):
    """Register `trigger` on `table` if it doesn't exist."""
    trigger_name = "%s_%s" % (table, procedure)
    trigger_sql = dedent("""\
        DROP TRIGGER IF EXISTS %s ON %s;
        CREATE TRIGGER %s
        %s %s ON %s
        FOR EACH ROW EXECUTE PROCEDURE %s();
        """) % (
        trigger_name,
        table,
        trigger_name,
        when.upper(),
        event.upper(),
        table,
        procedure,
        )
    with closing(connection.cursor()) as cursor:
        cursor.execute(trigger_sql)


def register_procedure(procedure):
    """Register the `procedure` SQL."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(procedure)


@transactional
def register_all_triggers():
    """Register all triggers into the database."""
    register_procedure(NODE_CREATE_PROCEDURE)
    register_procedure(NODE_UPDATE_PROCEDURE)
    register_procedure(NODE_DELETE_PROCEDURE)
    register_trigger("maasserver_node", "node_create_notify", "insert")
    register_trigger("maasserver_node", "node_update_notify", "update")
    register_trigger("maasserver_node", "node_delete_notify", "delete")
