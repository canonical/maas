from django.db import migrations, models

import maasserver.migrations.fields


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0119_set_default_vlan_field")]

    operations = [
        migrations.AddField(
            model_name="bootsourcecache",
            name="extra",
            field=maasserver.migrations.fields.JSONObjectField(
                blank=True, default="", editable=False
            ),
        )
    ]
