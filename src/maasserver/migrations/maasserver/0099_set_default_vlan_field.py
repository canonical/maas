from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.subnet


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0098_add_space_to_vlan")]

    operations = [
        migrations.AlterField(
            model_name="subnet",
            name="vlan",
            field=models.ForeignKey(
                to="maasserver.VLAN",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        )
    ]
