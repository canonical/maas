import django.contrib.postgres.fields
from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0106_testing_status")]

    operations = [
        migrations.CreateModel(
            name="PodHints",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        auto_created=True,
                        serialize=False,
                        primary_key=True,
                    ),
                ),
                ("cores", models.IntegerField(default=0)),
                ("memory", models.IntegerField(default=0)),
                ("local_storage", models.BigIntegerField(default=0)),
                ("local_disks", models.IntegerField(default=-1)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.RemoveField(model_name="chassishints", name="chassis"),
        migrations.DeleteModel(name="Chassis"),
        migrations.DeleteModel(name="Storage"),
        migrations.CreateModel(
            name="Pod",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.bmc",),
        ),
        migrations.AddField(
            model_name="bmc",
            name="architectures",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(),
                size=None,
                null=True,
                default=list,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="bmc",
            name="bmc_type",
            field=models.IntegerField(
                editable=False, choices=[(0, "BMC"), (1, "POD")], default=0
            ),
        ),
        migrations.AddField(
            model_name="bmc",
            name="capabilities",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(),
                size=None,
                null=True,
                default=list,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="bmc",
            name="cores",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bmc",
            name="cpu_speed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bmc",
            name="local_disks",
            field=models.IntegerField(default=-1),
        ),
        migrations.AddField(
            model_name="bmc",
            name="local_storage",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bmc",
            name="memory",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bmc",
            name="name",
            field=models.CharField(
                max_length=255, default="", unique=False, blank=True
            ),
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
        migrations.DeleteModel(name="ChassisHints"),
        migrations.AddField(
            model_name="podhints",
            name="pod",
            field=models.OneToOneField(
                related_name="hints",
                to="maasserver.BMC",
                on_delete=models.CASCADE,
            ),
        ),
    ]
