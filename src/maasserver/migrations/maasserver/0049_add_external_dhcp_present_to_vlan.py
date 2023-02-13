from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0048_add_subnet_allow_proxy")]

    operations = [
        migrations.AddField(
            model_name="vlan",
            name="external_dhcp_present",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AlterField(
            model_name="interface",
            name="vlan",
            field=models.ForeignKey(
                to="maasserver.VLAN",
                on_delete=django.db.models.deletion.PROTECT,
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="subnet",
            name="vlan",
            field=models.ForeignKey(
                to="maasserver.VLAN",
                on_delete=django.db.models.deletion.PROTECT,
                default=0,
            ),
        ),
    ]
