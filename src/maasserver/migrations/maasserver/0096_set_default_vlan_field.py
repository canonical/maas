from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0095_vlan_relay_vlan")]

    operations = [
        migrations.AlterField(
            model_name="subnet",
            name="vlan",
            field=models.ForeignKey(
                to="maasserver.VLAN",
                default=lambda: 0,
                on_delete=django.db.models.deletion.PROTECT,
            ),
        )
    ]
