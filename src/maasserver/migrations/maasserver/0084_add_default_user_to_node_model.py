from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0083_device_discovery")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="default_user",
            field=models.CharField(blank=True, max_length=32, default=""),
        )
    ]
