# -*- coding: utf-8 -*-
from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0076_interface_discovery_rescue_mode")]

    operations = [
        migrations.CreateModel(
            name="StaticRoute",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "gateway_ip",
                    models.GenericIPAddressField(verbose_name="Gateway IP"),
                ),
                ("metric", models.PositiveIntegerField()),
                (
                    "destination",
                    models.ForeignKey(
                        related_name="+",
                        to="maasserver.Subnet",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        related_name="+",
                        to="maasserver.Subnet",
                        on_delete=models.CASCADE,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name="staticroute",
            unique_together={("source", "destination", "gateway_ip")},
        ),
    ]
