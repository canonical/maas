from django.conf import settings
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maasserver", "0135_add_pool_reference_to_node"),
    ]

    operations = [
        migrations.CreateModel(
            name="Role",
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
                    "name",
                    models.CharField(
                        validators=[
                            django.core.validators.RegexValidator(
                                "^\\w[ \\w-]*$"
                            )
                        ],
                        max_length=255,
                        unique=True,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "resource_pools",
                    models.ManyToManyField(to="maasserver.ResourcePool"),
                ),
                ("users", models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
        )
    ]
