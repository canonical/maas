import django.contrib.postgres.fields
from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0071_ntp_server_to_ntp_servers")]

    operations = [
        migrations.CreateModel(
            name="PackageRepository",
            fields=[
                (
                    "id",
                    models.AutoField(
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(default="", unique=True, max_length=41),
                ),
                ("description", models.TextField(blank=True, default="")),
                (
                    "url",
                    models.URLField(
                        help_text="The URL of the PackageRepository."
                    ),
                ),
                (
                    "distro",
                    models.CharField(
                        editable=False, max_length=41, default="ubuntu"
                    ),
                ),
                (
                    "pockets",
                    django.contrib.postgres.fields.ArrayField(
                        blank=True,
                        size=None,
                        null=True,
                        default=list,
                        base_field=models.TextField(),
                    ),
                ),
                (
                    "components",
                    django.contrib.postgres.fields.ArrayField(
                        blank=True,
                        size=None,
                        null=True,
                        default=list,
                        base_field=models.TextField(),
                    ),
                ),
                (
                    "arches",
                    django.contrib.postgres.fields.ArrayField(
                        blank=True,
                        size=None,
                        null=True,
                        default=list,
                        base_field=models.TextField(),
                    ),
                ),
                ("key", models.TextField(editable=False, default="")),
                ("default", models.BooleanField(default=False)),
                ("enabled", models.BooleanField(default=True)),
            ],
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        )
    ]
