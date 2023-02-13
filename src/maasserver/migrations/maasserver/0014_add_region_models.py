import django.core.validators
from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.cleansave
import maasserver.models.node


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0013_remove_boot_type_from_node")]

    operations = [
        migrations.CreateModel(
            name="RegionControllerProcess",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        primary_key=True,
                        serialize=False,
                        auto_created=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("pid", models.IntegerField()),
            ],
            options={"ordering": ["pid"]},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="RegionControllerProcessEndpoint",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        primary_key=True,
                        serialize=False,
                        auto_created=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("address", models.GenericIPAddressField(editable=False)),
                (
                    "port",
                    models.IntegerField(
                        default=0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(65535),
                        ],
                    ),
                ),
                (
                    "process",
                    models.ForeignKey(
                        to="maasserver.RegionControllerProcess",
                        related_name="endpoints",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="RegionController",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.node",),
        ),
        migrations.AlterField(
            model_name="node",
            name="node_type",
            field=models.IntegerField(
                editable=False,
                choices=[
                    (0, "Machine"),
                    (1, "Device"),
                    (2, "Rack controller"),
                    (3, "Region controller"),
                    (4, "Region and rack controller"),
                ],
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="node",
            name="nodegroup",
            field=models.ForeignKey(
                blank=True,
                null=True,
                to="maasserver.NodeGroup",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="regioncontrollerprocess",
            name="region",
            field=models.ForeignKey(
                to="maasserver.Node",
                related_name="processes",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="dns_process",
            field=models.OneToOneField(
                editable=False,
                to="maasserver.RegionControllerProcess",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="regioncontrollerprocessendpoint",
            unique_together={("process", "address", "port")},
        ),
        migrations.AlterUniqueTogether(
            name="regioncontrollerprocess",
            unique_together={("region", "pid")},
        ),
    ]
