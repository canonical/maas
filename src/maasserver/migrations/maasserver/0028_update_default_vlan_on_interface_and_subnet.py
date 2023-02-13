from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.interface
import maasserver.models.subnet


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0027_replace_static_range_with_admin_reserved_ranges")
    ]

    operations = [
        migrations.AlterField(
            model_name="interface",
            name="vlan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="maasserver.VLAN",
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="subnet",
            name="vlan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="maasserver.VLAN",
                default=0,
            ),
        ),
    ]
