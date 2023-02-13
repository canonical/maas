from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.interface
import maasserver.models.subnet


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0055_dns_publications")]

    operations = [
        migrations.AddField(
            model_name="fabric",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="space",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="subnet",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="vlan",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="interface",
            name="vlan",
            field=models.ForeignKey(
                to="maasserver.VLAN",
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AlterField(
            model_name="subnet",
            name="vlan",
            field=models.ForeignKey(
                to="maasserver.VLAN",
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
    ]
