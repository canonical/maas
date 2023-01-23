from django.db import migrations, models
import django.db.models.deletion

import maasserver.migrations.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0014_add_region_models")]

    operations = [
        migrations.CreateModel(
            name="BMC",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        verbose_name="ID",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "power_type",
                    models.CharField(blank=True, default="", max_length=10),
                ),
                (
                    "power_parameters",
                    maasserver.migrations.fields.JSONObjectField(
                        blank=True, default="", max_length=32768
                    ),
                ),
                (
                    "ip_address",
                    models.ForeignKey(
                        editable=False,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        blank=True,
                        to="maasserver.StaticIPAddress",
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.RenameField(
            model_name="node",
            old_name="power_parameters",
            new_name="instance_power_parameters",
        ),
        migrations.AddField(
            model_name="node",
            name="bmc",
            field=models.ForeignKey(
                editable=False,
                null=True,
                to="maasserver.BMC",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="bmc",
            unique_together={("power_type", "power_parameters", "ip_address")},
        ),
    ]
