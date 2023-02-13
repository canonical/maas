from django.db import migrations, models

import maasserver.migrations.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0124_staticipaddress_address_family_index")
    ]

    operations = [
        migrations.CreateModel(
            name="Switch",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        primary_key=True,
                        auto_created=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "nos_driver",
                    models.CharField(max_length=64, blank=True, default=""),
                ),
                (
                    "nos_parameters",
                    maasserver.migrations.fields.JSONObjectField(
                        max_length=32768, blank=True, default=""
                    ),
                ),
                (
                    "node",
                    models.OneToOneField(
                        to="maasserver.Node", on_delete=models.CASCADE
                    ),
                ),
            ],
            options={
                "verbose_name": "Switch",
                "verbose_name_plural": "Switches",
            },
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        )
    ]
