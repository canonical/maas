# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Triggers

Triggers are implemented in the database to notify the PostgresListener when
an event occurs. Each trigger should use "CREATE OR REPLACE" so its overrides
its previous trigger. All triggers will be added into the database via the
`start_up` method for regiond.
"""

__all__ = [
    "register_all_triggers",
    "register_procedure",
    "register_trigger",
    ]

from contextlib import closing
from textwrap import dedent

from django.db import connection
from maasserver.utils.orm import transactional


def register_procedure(procedure):
    """Register the `procedure` SQL."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(procedure)


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


@transactional
def register_all_triggers():
    """Register all triggers into the database."""
    from maasserver.triggers.websocket import register_websocket_triggers
    register_websocket_triggers()
