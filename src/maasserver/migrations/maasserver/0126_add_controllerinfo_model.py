from django.db import migrations, models

import maasserver.migrations.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0125_add_switch_model")]

    operations = [
        migrations.CreateModel(
            name="ControllerInfo",
            fields=[
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "node",
                    models.OneToOneField(
                        serialize=False,
                        primary_key=True,
                        to="maasserver.Node",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "version",
                    models.CharField(blank=True, null=True, max_length=255),
                ),
                (
                    "interfaces",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", blank=True, max_length=32768
                    ),
                ),
                (
                    "interface_update_hints",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", blank=True, max_length=32768
                    ),
                ),
            ],
            options={"verbose_name": "ControllerInfo"},
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.RemoveField(model_name="switch", name="id"),
        migrations.AlterField(
            model_name="switch",
            name="node",
            field=models.OneToOneField(
                serialize=False,
                primary_key=True,
                to="maasserver.Node",
                on_delete=models.CASCADE,
            ),
        ),
    ]
