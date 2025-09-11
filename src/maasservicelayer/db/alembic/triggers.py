#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Triggers

Triggers are implemented in the database to notify the PostgresListener when
an event occurs.

IMPORTANT: This code is used by Alembic migrations to create triggers. Any modification may alter those migrations, potentially causing issues when setting up new environments. Please take extra care to avoid introducing breaking changes!
"""

from textwrap import dedent

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


def register_procedure(op, procedure):
    """Register the `procedure` SQL."""
    op.execute(procedure)


def register_triggers(
    op,
    table,
    event_prefix,
    params=None,
    fields=None,
    events=EVENTS_CUD,
    when="after",
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
    for pg_event, maas_event_type, pg_obj in events:
        event_params = None
        if params is not None:
            event_params = {
                f"{pg_obj}.{key}": value for key, value in params.items()
            }

        register_trigger(
            op,
            table,
            f"{event_prefix}_{maas_event_type}_notify",
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
    if params is None:
        params = {}
    if fields is None:
        fields = []

    clauses = []
    if params:
        clauses.extend(f"{key} = '{value}'" for key, value in params.items())
    if is_update and fields:
        clauses.append(
            "("
            + " OR ".join(
                f"NEW.{field} IS DISTINCT FROM OLD.{field}" for field in fields
            )
            + ")"
        )
    if not clauses:
        return ""
    and_clauses = " AND ".join(clauses)
    return f"WHEN ({and_clauses})"


def register_trigger(
    op, table, procedure, event, params=None, fields=None, when="after"
):
    """(Re-)create `trigger` on `table`."""
    table_name = table
    if table.startswith("maasserver_"):
        table_name = table_name[11:]
    trigger_name = f"{table_name}_{procedure}"
    is_update = event == "update"
    when_clause = _make_when_clause(is_update, params, fields)
    drop_trigger_sql = dedent(
        f"""\
        DROP TRIGGER IF EXISTS {trigger_name} ON {table};
        """
    )
    register_procedure(op, drop_trigger_sql)
    create_trigger_sql = dedent(
        f"""
        CREATE TRIGGER {trigger_name}
        {when.upper()} {event.upper()} ON {table}
        FOR EACH ROW
        {when_clause}
        EXECUTE PROCEDURE {procedure}();
        """
    )
    register_procedure(op, create_trigger_sql)
