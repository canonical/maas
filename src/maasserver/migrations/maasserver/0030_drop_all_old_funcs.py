from django.db import connection, migrations, models


def drop_all_funcs(apps, schema_editor):
    """Drop all existing database functions as old functions have been
    renamed or are no longer necessary. The functions which are required
    will be recreated on region startup.
    """
    # with connection.cursor() as cursor:
    #     cursor.execute(
    #         "SELECT ns.nspname || '.' || proname || '(' || "
    #         "oidvectortypes(proargtypes) || ')' FROM pg_proc INNER JOIN "
    #         "pg_namespace ns ON (pg_proc.pronamespace = ns.oid) "
    #         "WHERE ns.nspname = 'public';"
    #     )
    #     for row in cursor.fetchall():
    #         cursor.execute("DROP FUNCTION %s CASCADE;" % row[0])

    # Fix for LP: 2097079
    #
    # Turn this migration as a noop to avoid dropping the entire list of
    # functions belonging to pg_proc table. Since the same table can contain
    # functions from PostgreSQL plugins, like pgaudit, btree_gin, etc., it is
    # dangerous to blindly dropping all of them. In addition, purpose of this
    # migration was to delete any functions that were introduced in
    # MAAS < 2.0, used by database triggers, and views. Since the functions
    # are no longer used by MAAS >= 2.0 or they are added from Python with
    # CREATE OR REPLACE, it is safe to turn this into noop. For further
    # protection, migrating MAAS from 1.x directly to >= 3.5 should be
    # avoided. This should already be the case for other reasons, including
    # this one.

    pass


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0029_add_rdns_mode")]

    operations = [migrations.RunPython(drop_all_funcs)]
