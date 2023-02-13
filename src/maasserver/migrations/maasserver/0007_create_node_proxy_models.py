import django.contrib.postgres.fields
from django.db import migrations, models

import maasserver.fields


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0006_add_lease_time_to_staticipaddress")]

    operations = [
        migrations.CreateModel(
            name="Machine",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.node",),
        ),
        migrations.CreateModel(
            name="RackController",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.node",),
        ),
    ]
