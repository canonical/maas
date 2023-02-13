from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0003_remove_noderesult")]

    operations = [
        migrations.AlterField(
            model_name="scriptresult",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "Pending"),
                    (1, "Running"),
                    (2, "Passed"),
                    (3, "Failed"),
                    (4, "Timed out"),
                    (5, "Aborted"),
                ],
                default=0,
            ),
        )
    ]
