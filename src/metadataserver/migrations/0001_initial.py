from django.db import migrations, models

import maasserver.models.cleansave
import metadataserver.fields


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0001_initial"),
        ("piston3", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommissioningScript",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(unique=True, max_length=255)),
                ("content", metadataserver.fields.BinaryField()),
            ],
        ),
        migrations.CreateModel(
            name="NodeKey",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        unique=True, max_length=18, editable=False
                    ),
                ),
                (
                    "node",
                    models.OneToOneField(
                        editable=False,
                        to="maasserver.Node",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "token",
                    models.OneToOneField(
                        editable=False,
                        to="piston3.Token",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="NodeResult",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("script_result", models.IntegerField(editable=False)),
                (
                    "result_type",
                    models.IntegerField(
                        default=0,
                        editable=False,
                        choices=[(0, "Commissioning"), (1, "Installation")],
                    ),
                ),
                ("name", models.CharField(max_length=255, editable=False)),
                (
                    "data",
                    metadataserver.fields.BinaryField(
                        default=b"", max_length=1048576, blank=True
                    ),
                ),
                (
                    "node",
                    models.ForeignKey(
                        editable=False,
                        to="maasserver.Node",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="NodeUserData",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("data", metadataserver.fields.BinaryField()),
                (
                    "node",
                    models.OneToOneField(
                        editable=False,
                        to="maasserver.Node",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name="noderesult", unique_together={("node", "name")}
        ),
    ]
