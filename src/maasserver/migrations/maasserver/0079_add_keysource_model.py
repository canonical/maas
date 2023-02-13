# -*- coding: utf-8 -*-
from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0078_remove_packagerepository_description")
    ]

    operations = [
        migrations.CreateModel(
            name="KeySource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        serialize=False,
                        primary_key=True,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "protocol",
                    models.CharField(
                        max_length=64,
                        choices=[("lp", "launchpad"), ("gh", "github")],
                    ),
                ),
                ("auth_id", models.CharField(max_length=255)),
                ("auto_update", models.BooleanField(default=False)),
            ],
            options={"verbose_name": "Key Source"},
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.AddField(
            model_name="sshkey",
            name="keysource",
            field=models.ForeignKey(
                to="maasserver.KeySource",
                editable=False,
                blank=True,
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="sshkey", unique_together={("user", "key", "keysource")}
        ),
    ]
