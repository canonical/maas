from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0109_bmc_names_unique")]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="category",
            field=models.CharField(
                choices=[
                    ("error", "Error"),
                    ("warning", "Warning"),
                    ("success", "Success"),
                    ("info", "Informational"),
                ],
                max_length=10,
                default="info",
            ),
        )
    ]
