# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import migrations, models

import maasserver.migrations.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maasserver", "0102_remove_space_from_subnet"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        verbose_name="ID",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "ident",
                    models.CharField(null=True, blank=True, max_length=40),
                ),
                ("users", models.BooleanField(default=False)),
                ("admins", models.BooleanField(default=False)),
                ("message", models.TextField(blank=True)),
                (
                    "context",
                    maasserver.migrations.fields.JSONObjectField(
                        default=dict, blank=True
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        to=settings.AUTH_USER_MODEL,
                        blank=True,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.RunSQL(
            # Forwards.
            "CREATE UNIQUE INDEX maasserver_notification_ident "
            "ON maasserver_notification (ident) "
            "WHERE ident IS NOT NULL",
            # Reverse.
            "DROP INDEX maasserver_notification_ident",
        ),
    ]
