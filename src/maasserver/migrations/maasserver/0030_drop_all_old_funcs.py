from django.db import connection, migrations, models


def drop_all_funcs(apps, schema_editor):
    """Drop all existing database functions as old functions have been
    renamed or are no longer neccessary. The functions which are required
    will be recreated on region startup.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ns.nspname || '.' || proname || '(' || "
            "oidvectortypes(proargtypes) || ')' FROM pg_proc INNER JOIN "
            "pg_namespace ns ON (pg_proc.pronamespace = ns.oid) "
            "WHERE ns.nspname = 'public';"
        )
        for row in cursor.fetchall():
            cursor.execute("DROP FUNCTION %s CASCADE;" % row[0])


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0029_add_rdns_mode")]

    operations = [migrations.RunPython(drop_all_funcs)]
