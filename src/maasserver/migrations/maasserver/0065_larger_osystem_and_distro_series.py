from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0064_remove_unneeded_event_triggers")]

    operations = [
        migrations.AlterField(
            model_name="node",
            name="distro_series",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="node",
            name="osystem",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
    ]
