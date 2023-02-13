from django.db import migrations, models
import django.db.models.deletion

import maasserver.fields


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0049_add_external_dhcp_present_to_vlan")]

    operations = [
        migrations.RemoveField(
            model_name="vlan", name="external_dhcp_present"
        ),
        migrations.AddField(
            model_name="vlan",
            name="external_dhcp",
            field=models.GenericIPAddressField(
                null=True, editable=False, default=None, blank=True
            ),
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
