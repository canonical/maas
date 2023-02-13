import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadataserver", "0016_script_model_fw_update_and_hw_config")
    ]

    operations = [
        migrations.AddField(
            model_name="scriptset",
            name="requested_scripts",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(),
                default=list,
                blank=True,
                null=True,
                size=None,
            ),
        )
    ]
