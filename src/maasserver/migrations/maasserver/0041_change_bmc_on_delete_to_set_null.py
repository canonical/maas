from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0040_fix_id_seq")]

    operations = [
        migrations.AlterField(
            model_name="bmc",
            name="ip_address",
            field=models.ForeignKey(
                editable=False,
                default=None,
                blank=True,
                to="maasserver.StaticIPAddress",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
            ),
        )
    ]
