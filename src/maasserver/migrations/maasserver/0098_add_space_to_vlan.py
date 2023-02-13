from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.subnet


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0097_node_chassis_storage_hints")]

    operations = [
        migrations.AddField(
            model_name="vlan",
            name="space",
            field=models.ForeignKey(
                blank=True,
                null=True,
                to="maasserver.Space",
                on_delete=django.db.models.deletion.SET_NULL,
            ),
        )
    ]
