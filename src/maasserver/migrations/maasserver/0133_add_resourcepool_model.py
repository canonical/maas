import django.core.validators
from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0132_consistent_model_name_validation")]

    operations = [
        migrations.CreateModel(
            name="ResourcePool",
            fields=[
                (
                    "id",
                    models.AutoField(
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        validators=[
                            django.core.validators.RegexValidator(
                                "^\\w[ \\w-]*$"
                            )
                        ],
                        max_length=256,
                        unique=True,
                    ),
                ),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ["name"]},
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        )
    ]
