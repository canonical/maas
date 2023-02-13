from django.db import migrations, models

import metadataserver.fields


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0011_script_metadata")]

    operations = [
        migrations.AlterField(
            model_name="scriptresult",
            name="result",
            field=metadataserver.fields.BinaryField(
                max_length=1048576, blank=True, default=b""
            ),
        ),
        migrations.AlterField(
            model_name="scriptresult",
            name="status",
            field=models.IntegerField(
                default=0,
                choices=[
                    (0, "Pending"),
                    (1, "Running"),
                    (2, "Passed"),
                    (3, "Failed"),
                    (4, "Timed out"),
                    (5, "Aborted"),
                    (6, "Degraded"),
                    (7, "Installing dependencies"),
                    (8, "Failed installing dependencies"),
                ],
            ),
        ),
    ]
