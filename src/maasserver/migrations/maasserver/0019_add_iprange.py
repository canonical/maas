from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maasserver", "0018_add_dnsdata"),
    ]

    operations = [
        migrations.CreateModel(
            name="IPRange",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "type",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("dynamic", "Dynamic IP Range"),
                            ("reserved", "Reserved"),
                            (
                                "managed_static",
                                "MAAS Managed Static IP Addresses",
                            ),
                        ],
                    ),
                ),
                (
                    "start_ip",
                    models.GenericIPAddressField(
                        verbose_name="Start IP", editable=False
                    ),
                ),
                (
                    "end_ip",
                    models.GenericIPAddressField(
                        verbose_name="End IP", editable=False
                    ),
                ),
                (
                    "comment",
                    models.CharField(max_length=255, null=True, blank=True),
                ),
                (
                    "subnet",
                    models.ForeignKey(
                        to="maasserver.Subnet", on_delete=models.CASCADE
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        editable=False,
                        default=None,
                        to=settings.AUTH_USER_MODEL,
                        blank=True,
                    ),
                ),
            ],
            options={"abstract": False},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        )
    ]
