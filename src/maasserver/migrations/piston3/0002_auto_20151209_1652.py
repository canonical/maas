from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("piston3", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="consumer",
            name="status",
            field=models.CharField(
                default="pending",
                choices=[
                    ("pending", "Pending"),
                    ("accepted", "Accepted"),
                    ("canceled", "Canceled"),
                    ("rejected", "Rejected"),
                ],
                max_length=16,
            ),
        )
    ]
