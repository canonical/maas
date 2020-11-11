# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Triggers

Triggers are implemented in the database to notify the PostgresListener when
an event occurs. Each trigger should use "CREATE OR REPLACE" so its overrides
its previous trigger. All triggers will be added into the database via the
`start_up` method for regiond.
"""


from contextlib import closing
from textwrap import dedent

from django.db import connection

from maasserver.utils.orm import transactional


def register_procedure(procedure):
    """Register the `procedure` SQL."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(procedure)


# Mappings for  (postgres_event_type, maas_notification_type, pg_obj) for
# trigger notification events. Three conventions are currently in-use in MAAS.

# Event names: create/update/delete.
# The majority of triggers use this convention; this is the default.
EVENTS_CUD = (
    ("insert", "create", "NEW"),
    ("update", "update", "NEW"),
    ("delete", "delete", "OLD"),
)

# Event names: insert/update/delete.
EVENTS_IUD = (
    ("insert", "insert", "NEW"),
    ("update", "update", "NEW"),
    ("delete", "delete", "OLD"),
)

# Event names: link/update/unlink.
EVENTS_LUU = (
    ("insert", "link", "NEW"),
    ("update", "update", "NEW"),
    ("delete", "unlink", "OLD"),
)

# Event names: link/unlink.
EVENTS_LU = (("insert", "link", "NEW"), ("delete", "unlink", "OLD"))


def register_triggers(
    table, event_prefix, params=None, fields=None, events=None, when="after"
):
    """Registers a set of triggers for insert, update, and delete.

    Event names will be determined based on MAAS convention, unless the
    convention is passed in via the `events` parameter. Predefined conventions
    in-use in MAAS are provided via the EVENTS_* constants.

    :param table: The table name to create the trigger on.
    :param event_prefix: The event prefix for the trigger. For example, if
        the table is maasserver_subnet, 'subnet' might be an appropriate event
        prefix.
    :param params: A dictionary of parameters that should be ANDed together to
        form the initial WHEN clause.
    :param fields: A list of fields whose values will be checked for changes
        before the trigger fires. If None is specified, all fields in the row
        will be checked.
    :param events: A tuple in the format of the EVENTS_* constants indicating
        which convention to use for notification names.
    :param when: When the trigger should fire relative to the row update. The
        default is AFTER, but postgresql also supports BEFORE and INSTEAD OF.
    """
    if events is None:
        events = EVENTS_CUD
    for pg_event, maas_event_type, pg_obj in events:
        event_params = None
        if params is not None:
            event_params = {}
            for key, value in params.items():
                event_params["%s.%s" % (pg_obj, key)] = value
        register_trigger(
            table,
            "%s_%s_notify" % (event_prefix, maas_event_type),
            pg_event,
            event_params,
            fields,
            when,
        )


def _make_when_clause(is_update, params, fields):
    """Generates a WHEN clause for the trigger.

    :param is_update: If true, this trigger is for update. (not insert/delete)
    :param params: A dictionary of parameters that should be ANDed together to
        form the initial WHEN clause.
    :param fields: A list of fields whose values will be checked for changes
        before the trigger fires. If None is specified, all fields in the row
        will be checked.
    :return: the WHEN clause to use in the trigger.
    """
    when_clause = ""
    if params is not None or (fields is not None and is_update):
        if params is None:
            params = {}
        if fields is None:
            fields = []
        when_clause = "WHEN ("
        when_clause += " AND ".join(
            ["%s = '%s'" % (key, value) for key, value in params.items()]
        )
        if is_update and len(fields) > 0:
            if len(params) > 0:
                when_clause += " AND ("
            when_clause += " OR ".join(
                [
                    "NEW.%s IS DISTINCT FROM OLD.%s" % (field, field)
                    for field in fields
                ]
            )
            if len(params) > 0:
                when_clause += ")"
        when_clause += ")"
    return when_clause


def register_trigger(
    table, procedure, event, params=None, fields=None, when="after"
):
    """Register `trigger` on `table` if it doesn't exist."""
    # Strip the "maasserver_" off the front of the table name.
    table_name = table
    if table.startswith("maasserver_"):
        table_name = table_name[11:]
    trigger_name = "%s_%s" % (table_name, procedure)
    is_update = event == "update"
    when_clause = _make_when_clause(is_update, params, fields)
    trigger_sql = dedent(
        """\
        DROP TRIGGER IF EXISTS {trigger_name} ON {table};
        CREATE TRIGGER {trigger_name}
        {when} {event} ON {table}
        FOR EACH ROW
        {when_clause}
        EXECUTE PROCEDURE {procedure}();
        """
    )
    trigger_sql = trigger_sql.format(
        trigger_name=trigger_name,
        table=table,
        when=when.upper(),
        event=event.upper(),
        when_clause=when_clause,
        procedure=procedure,
    )
    with closing(connection.cursor()) as cursor:
        cursor.execute(trigger_sql)


@transactional
def register_all_triggers():
    """Register all triggers into the database."""
    from maasserver.triggers.system import register_system_triggers
    from maasserver.triggers.websocket import register_websocket_triggers

    register_system_triggers()
    register_websocket_triggers()
