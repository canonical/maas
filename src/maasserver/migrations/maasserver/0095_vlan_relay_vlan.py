from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0094_add_unmanaged_subnets")]

    operations = [
        migrations.AddField(
            model_name="vlan",
            name="relay_vlan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="relay_vlans",
                to="maasserver.VLAN",
            ),
        )
    ]
