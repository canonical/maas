# Generated by Django 3.2.12 on 2024-06-12 19:31

import re

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0328_merge_0327_and_0324"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservedIP",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "ip",
                    models.GenericIPAddressField(
                        unique=True, verbose_name="IP address"
                    ),
                ),
                (
                    "mac_address",
                    models.TextField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="'%(value)s' is not a valid MAC address.",
                                regex=re.compile(
                                    "^([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}$"
                                ),
                            )
                        ],
                        verbose_name="MAC address",
                    ),
                ),
                (
                    "comment",
                    models.CharField(
                        blank=True, default="", max_length=255, null=True
                    ),
                ),
                (
                    "subnet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="maasserver.subnet",
                    ),
                ),
                (
                    "vlan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="maasserver.vlan",
                        verbose_name="VLAN",
                    ),
                ),
            ],
            options={
                "verbose_name": "Reserved IP",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AddConstraint(
            model_name="reservedip",
            constraint=models.UniqueConstraint(
                fields=("mac_address", "vlan"),
                name="maasserver_reservedip_mac_address_vlan_uniq",
            ),
        ),
    ]
