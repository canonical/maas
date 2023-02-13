from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0031_add_region_rack_rpc_conn_model")]

    operations = [
        migrations.AlterField(
            model_name="vlan",
            name="primary_rack",
            field=models.ForeignKey(
                blank=True,
                null=True,
                related_name="+",
                to="maasserver.RackController",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterField(
            model_name="vlan",
            name="secondary_rack",
            field=models.ForeignKey(
                blank=True,
                null=True,
                related_name="+",
                to="maasserver.RackController",
                on_delete=models.CASCADE,
            ),
        ),
    ]
