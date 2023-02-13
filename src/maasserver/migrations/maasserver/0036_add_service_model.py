from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0035_convert_ether_wake_to_manual_power_type")
    ]

    operations = [
        migrations.CreateModel(
            name="Service",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        primary_key=True,
                        auto_created=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        help_text="Name of service. (e.g. maas-dhcpd)",
                        editable=False,
                        max_length=255,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        default="unknown",
                        choices=[
                            ("unknown", "Unknown"),
                            ("running", "Running"),
                            ("degraged", "Degraded"),
                            ("dead", "Dead"),
                            ("off", "Off"),
                        ],
                        editable=False,
                        max_length=10,
                    ),
                ),
                (
                    "status_info",
                    models.CharField(
                        blank=True, editable=False, max_length=255
                    ),
                ),
                (
                    "node",
                    models.ForeignKey(
                        to="maasserver.Node",
                        editable=False,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={"ordering": ["id"]},
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="service", unique_together={("node", "name")}
        ),
    ]
