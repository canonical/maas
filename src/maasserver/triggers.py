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
from maasserver.utils.orm import transactional

# Note that the corresponding test module (test_triggers) only tests that the
# triggers and procedures are registered.  The behavior of these procedures
# is tested (end-to-end testing) in test_listeners.  We test it there because
# the asynchronous nature of the PG events makes it easier to test in
# test_listeners where all the Twisted infrastructure is already in place.


def get_notification_procedure(proc_name, event_name, cast):
    return dedent("""\
        CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
        DECLARE
        BEGIN
          PERFORM pg_notify('%s',CAST(%s AS text));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """ % (proc_name, event_name, cast))


def register_trigger(table, procedure, event, params=None, when="after"):
    """Register `trigger` on `table` if it doesn't exist."""
    trigger_name = "%s_%s" % (table, procedure)
    if params is not None:
        filter = 'WHEN (' + ''.join(
            [
                "%s = '%s'" % (key, value)
                for key, value in params.items()
            ]) + ')'
    else:
        filter = ''
    trigger_sql = dedent("""\
        DROP TRIGGER IF EXISTS %s ON %s;
        CREATE TRIGGER %s
        %s %s ON %s
        FOR EACH ROW
        %s
        EXECUTE PROCEDURE %s();
        """) % (
        trigger_name,
        table,
        trigger_name,
        when.upper(),
        event.upper(),
        table,
        filter,
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
    # Register all the procedures.
    register_procedure(
        get_notification_procedure(
            'node_create_notify', 'node_create', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'node_update_notify', 'node_update', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'node_delete_notify', 'node_delete', 'OLD.system_id'))
    register_procedure(
        get_notification_procedure(
            'device_create_notify', 'device_create', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'device_update_notify', 'device_update', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'device_delete_notify', 'device_delete', 'OLD.system_id'))
    # Register the triggers.
    register_trigger(
        "maasserver_node", "node_create_notify", "insert",
        {'NEW.installable': True})
    register_trigger(
        "maasserver_node", "node_update_notify", "update",
        {'NEW.installable': True})
    register_trigger(
        "maasserver_node", "node_delete_notify", "delete",
        {'OLD.installable': True})
    register_trigger(
        "maasserver_node", "device_create_notify", "insert",
        {'NEW.installable': False})
    register_trigger(
        "maasserver_node", "device_update_notify", "update",
        {'NEW.installable': False})
    register_trigger(
        "maasserver_node", "device_delete_notify", "delete",
        {'OLD.installable': False})
