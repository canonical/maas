# -*- coding: utf-8 -*-
from django.db import migrations, models

import maasserver.migrations.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0092_rolling")]

    operations = [
        migrations.CreateModel(
            name="RDNS",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        verbose_name="ID",
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "ip",
                    models.GenericIPAddressField(
                        editable=False, verbose_name="IP"
                    ),
                ),
                ("hostname", models.CharField(max_length=256, null=True)),
                ("hostnames", maasserver.migrations.fields.JSONObjectField()),
                (
                    "observer",
                    models.ForeignKey(
                        to="maasserver.Node",
                        editable=False,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Reverse-DNS entries",
                "verbose_name": "Reverse-DNS entry",
            },
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="rdns", unique_together={("ip", "observer")}
        ),
    ]
