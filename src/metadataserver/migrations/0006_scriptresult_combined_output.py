from django.db import migrations, models

import metadataserver.fields


class Migration(migrations.Migration):
    dependencies = [
        ("metadataserver", "0005_store_powerstate_on_scriptset_creation")
    ]

    operations = [
        migrations.AddField(
            model_name="scriptresult",
            name="output",
            field=metadataserver.fields.BinaryField(
                blank=True, default=b"", max_length=1048576
            ),
        )
    ]
