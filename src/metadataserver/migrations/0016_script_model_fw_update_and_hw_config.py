import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0015_migrate_storage_tests")]

    operations = [
        migrations.AddField(
            model_name="script",
            name="for_hardware",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=255),
                size=None,
                default=list,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="script",
            name="may_reboot",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="script",
            name="recommission",
            field=models.BooleanField(default=False),
        ),
    ]
