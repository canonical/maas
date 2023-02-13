from django.conf import settings
from django.db import migrations, models
import piston3.models


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Consumer",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("key", models.CharField(max_length=18)),
                ("secret", models.CharField(max_length=32)),
                (
                    "status",
                    models.CharField(
                        default=b"pending",
                        max_length=16,
                        choices=[
                            (b"pending", b"Pending"),
                            (b"accepted", b"Accepted"),
                            (b"canceled", b"Canceled"),
                            (b"rejected", b"Rejected"),
                        ],
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        related_name="consumers",
                        blank=True,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Nonce",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("token_key", models.CharField(max_length=18)),
                ("consumer_key", models.CharField(max_length=18)),
                ("key", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="Token",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("key", models.CharField(max_length=18)),
                ("secret", models.CharField(max_length=32)),
                ("verifier", models.CharField(max_length=10)),
                (
                    "token_type",
                    models.IntegerField(
                        choices=[(1, "Request"), (2, "Access")]
                    ),
                ),
                (
                    "timestamp",
                    models.IntegerField(
                        default=piston3.models.get_default_timestamp
                    ),
                ),
                ("is_approved", models.BooleanField(default=False)),
                (
                    "callback",
                    models.CharField(max_length=255, null=True, blank=True),
                ),
                ("callback_confirmed", models.BooleanField(default=False)),
                (
                    "consumer",
                    models.ForeignKey(
                        to="piston3.Consumer", on_delete=models.CASCADE
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        related_name="tokens",
                        blank=True,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        ),
    ]
