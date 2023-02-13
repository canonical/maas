import django.core.validators
from django.db import migrations, models

import maasserver.models.dnspublication


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0054_controller")]

    operations = [
        migrations.CreateModel(
            name="DNSPublication",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        verbose_name="ID",
                        serialize=False,
                        primary_key=True,
                    ),
                ),
                (
                    "serial",
                    models.IntegerField(
                        editable=False,
                        default=maasserver.models.dnspublication.next_serial,
                        validators=(
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(
                                4294967295
                            ),
                        ),
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        editable=False,
                        max_length=255,
                        help_text="A brief explanation why DNS was published.",
                    ),
                ),
            ],
        )
    ]
