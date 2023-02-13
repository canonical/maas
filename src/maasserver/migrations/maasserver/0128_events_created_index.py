from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0127_nodemetadata")]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX maasserver_event__created ON maasserver_event(created)",
            "DROP INDEX maasserver_event__created",
        )
    ]
