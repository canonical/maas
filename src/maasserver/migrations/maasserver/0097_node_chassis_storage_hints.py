from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.cleansave
import maasserver.models.node


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0096_set_default_vlan_field")]

    operations = [
        migrations.CreateModel(
            name="ChassisHints",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                        auto_created=True,
                        verbose_name="ID",
                    ),
                ),
                ("cores", models.IntegerField(default=0)),
                ("memory", models.IntegerField(default=0)),
                ("local_storage", models.IntegerField(default=0)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Chassis",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.node",),
        ),
        migrations.CreateModel(
            name="Storage",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.node",),
        ),
        migrations.AddField(
            model_name="node",
            name="cpu_speed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="node",
            name="dynamic",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="node",
            name="domain",
            field=models.ForeignKey(
                to="maasserver.Domain",
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
            ),
        ),
        migrations.AlterField(
            model_name="node",
            name="node_type",
            field=models.IntegerField(
                choices=[
                    (0, "Machine"),
                    (1, "Device"),
                    (2, "Rack controller"),
                    (3, "Region controller"),
                    (4, "Region and rack controller"),
                    (5, "Chassis"),
                    (6, "Storage"),
                ],
                default=0,
                editable=False,
            ),
        ),
        migrations.AddField(
            model_name="chassishints",
            name="chassis",
            field=models.OneToOneField(
                to="maasserver.Node",
                related_name="chassis_hints",
                on_delete=models.CASCADE,
            ),
        ),
    ]
