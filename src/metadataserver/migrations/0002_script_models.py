import datetime

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion

import maasserver.migrations.fields
import maasserver.models.cleansave
import metadataserver.fields


class Migration(migrations.Migration):

    dependencies = [
        ("maasserver", "0104_notifications_dismissals"),
        ("metadataserver", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Script",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        verbose_name="ID",
                        auto_created=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "tags",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        default=list,
                        base_field=models.TextField(),
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "script_type",
                    models.IntegerField(
                        default=2,
                        choices=[
                            (0, "Commissioning script"),
                            (2, "Testing script"),
                        ],
                    ),
                ),
                (
                    "timeout",
                    models.DurationField(default=datetime.timedelta(0)),
                ),
                ("destructive", models.BooleanField(default=False)),
                ("default", models.BooleanField(default=False)),
                (
                    "script",
                    models.OneToOneField(
                        to="maasserver.VersionedTextFile",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.CreateModel(
            name="ScriptResult",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        verbose_name="ID",
                        auto_created=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "status",
                    models.IntegerField(
                        default=0,
                        choices=[
                            (0, "Pending"),
                            (1, "Running"),
                            (2, "Passed"),
                            (3, "Failed"),
                            (4, "Timed out"),
                        ],
                    ),
                ),
                ("exit_status", models.IntegerField(blank=True, null=True)),
                (
                    "script_name",
                    models.CharField(
                        max_length=255, null=True, editable=False
                    ),
                ),
                (
                    "stdout",
                    metadataserver.fields.BinaryField(
                        default=b"", max_length=1048576, blank=True
                    ),
                ),
                (
                    "stderr",
                    metadataserver.fields.BinaryField(
                        default=b"", max_length=1048576, blank=True
                    ),
                ),
                (
                    "result",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", blank=True
                    ),
                ),
                (
                    "script",
                    models.ForeignKey(
                        blank=True,
                        to="metadataserver.Script",
                        editable=False,
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                    ),
                ),
            ],
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.CreateModel(
            name="ScriptSet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        verbose_name="ID",
                        auto_created=True,
                        serialize=False,
                    ),
                ),
                ("last_ping", models.DateTimeField(blank=True, null=True)),
                (
                    "result_type",
                    models.IntegerField(
                        default=0,
                        choices=[
                            (0, "Commissioning"),
                            (1, "Installation"),
                            (2, "Testing"),
                        ],
                        editable=False,
                    ),
                ),
                (
                    "node",
                    models.ForeignKey(
                        to="maasserver.Node", on_delete=models.CASCADE
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AlterField(
            model_name="noderesult",
            name="result_type",
            field=models.IntegerField(
                default=0,
                choices=[
                    (0, "Commissioning"),
                    (1, "Installation"),
                    (2, "Testing"),
                ],
                editable=False,
            ),
        ),
        migrations.AddField(
            model_name="scriptresult",
            name="script_set",
            field=models.ForeignKey(
                to="metadataserver.ScriptSet",
                editable=False,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="scriptresult",
            name="script_version",
            field=models.ForeignKey(
                blank=True,
                to="maasserver.VersionedTextFile",
                editable=False,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
            ),
        ),
    ]
