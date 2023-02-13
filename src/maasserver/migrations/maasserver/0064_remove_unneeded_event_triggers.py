from contextlib import closing

from django.db import connection, migrations


def remove_unneeded_event_triggers(apps, schema_editor):
    with closing(connection.cursor()) as cursor:
        cursor.execute(
            "DROP TRIGGER IF EXISTS event_event_update_notify ON "
            "maasserver_event;"
            "DROP TRIGGER IF EXISTS event_event_delete_notify ON "
            "maasserver_event;"
        )


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0063_remove_orphaned_bmcs_and_ips")]

    operations = [migrations.RunPython(remove_unneeded_event_triggers)]
