from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0038_filesystem_ramfs_tmpfs_support")]

    operations = [
        migrations.CreateModel(
            name="Template",
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
                    "filename",
                    models.CharField(
                        help_text="Template filename",
                        unique=True,
                        max_length=64,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Templates",
                "verbose_name": "Template",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="VersionedTextFile",
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
                    "data",
                    models.TextField(
                        help_text="File contents",
                        null=True,
                        editable=False,
                        blank=True,
                    ),
                ),
                (
                    "comment",
                    models.CharField(
                        help_text="Description of this version",
                        null=True,
                        max_length=255,
                        blank=True,
                    ),
                ),
                (
                    "previous_version",
                    models.ForeignKey(
                        related_name="next_versions",
                        to="maasserver.VersionedTextFile",
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "VersionedTextFiles",
                "verbose_name": "VersionedTextFile",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AddField(
            model_name="template",
            name="default_version",
            field=models.ForeignKey(
                related_name="default_templates",
                to="maasserver.VersionedTextFile",
                help_text="Default data for this template.",
                editable=False,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="version",
            field=models.ForeignKey(
                related_name="templates",
                blank=True,
                to="maasserver.VersionedTextFile",
                help_text="Custom data for this template.",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
    ]
