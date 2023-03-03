# -*- coding: utf-8 -*-
from django.db import migrations, models

import maasserver.fields
import maasserver.migrations.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0075_modify_packagerepository")]

    operations = [
        migrations.AddField(
            model_name="interface",
            name="acquired",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.CreateModel(
            name="MDNS",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        auto_created=True,
                        verbose_name="ID",
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "ip",
                    models.GenericIPAddressField(
                        null=True,
                        blank=True,
                        editable=False,
                        default=None,
                        verbose_name="IP",
                    ),
                ),
                ("hostname", models.CharField(null=True, max_length=256)),
                ("count", models.IntegerField(default=1)),
            ],
            options={
                "verbose_name_plural": "mDNS bindings",
                "verbose_name": "mDNS binding",
            },
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.CreateModel(
            name="Neighbour",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        auto_created=True,
                        verbose_name="ID",
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "ip",
                    models.GenericIPAddressField(
                        null=True,
                        blank=True,
                        editable=False,
                        default=None,
                        verbose_name="IP",
                    ),
                ),
                ("time", models.IntegerField()),
                ("vid", models.IntegerField(null=True, blank=True)),
                ("count", models.IntegerField(default=1)),
                (
                    "mac_address",
                    maasserver.migrations.fields.MACAddressField(
                        null=True, blank=True, editable=False
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Neighbours",
                "verbose_name": "Neighbour",
            },
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.AddField(
            model_name="interface",
            name="active_discovery_params",
            field=maasserver.migrations.fields.JSONObjectField(
                editable=False, default="", blank=True
            ),
        ),
        migrations.AddField(
            model_name="interface",
            name="active_discovery_state",
            field=models.BooleanField(editable=False, default=False),
        ),
        migrations.AddField(
            model_name="interface",
            name="mdns_discovery_state",
            field=models.BooleanField(editable=False, default=False),
        ),
        migrations.AddField(
            model_name="interface",
            name="neighbour_discovery_state",
            field=models.BooleanField(editable=False, default=False),
        ),
        migrations.AlterField(
            model_name="node",
            name="previous_status",
            field=models.IntegerField(
                choices=[
                    (0, "New"),
                    (1, "Commissioning"),
                    (2, "Failed commissioning"),
                    (3, "Missing"),
                    (4, "Ready"),
                    (5, "Reserved"),
                    (10, "Allocated"),
                    (9, "Deploying"),
                    (6, "Deployed"),
                    (7, "Retired"),
                    (8, "Broken"),
                    (11, "Failed deployment"),
                    (12, "Releasing"),
                    (13, "Releasing failed"),
                    (14, "Disk erasing"),
                    (15, "Failed disk erasing"),
                    (16, "Rescue mode"),
                    (17, "Entering rescue mode"),
                    (18, "Failed to enter rescue mode"),
                    (19, "Exiting rescue mode"),
                    (20, "Failed to exit rescue mode"),
                ],
                editable=False,
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="node",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "New"),
                    (1, "Commissioning"),
                    (2, "Failed commissioning"),
                    (3, "Missing"),
                    (4, "Ready"),
                    (5, "Reserved"),
                    (10, "Allocated"),
                    (9, "Deploying"),
                    (6, "Deployed"),
                    (7, "Retired"),
                    (8, "Broken"),
                    (11, "Failed deployment"),
                    (12, "Releasing"),
                    (13, "Releasing failed"),
                    (14, "Disk erasing"),
                    (15, "Failed disk erasing"),
                    (16, "Rescue mode"),
                    (17, "Entering rescue mode"),
                    (18, "Failed to enter rescue mode"),
                    (19, "Exiting rescue mode"),
                    (20, "Failed to exit rescue mode"),
                ],
                editable=False,
                default=0,
            ),
        ),
        migrations.AddField(
            model_name="neighbour",
            name="interface",
            field=models.ForeignKey(
                editable=False,
                to="maasserver.Interface",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="mdns",
            name="interface",
            field=models.ForeignKey(
                editable=False,
                to="maasserver.Interface",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="neighbour",
            unique_together={("interface", "vid", "mac_address", "ip")},
        ),
    ]
